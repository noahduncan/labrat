import logging
import os
import queue
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests

from labrat_client import flags
from labrat_client.exceptions import (
    LabratConfigError,
    LabratConnectionError,
    LabratError,
)
from labrat_client.worker import Worker

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Exposure:
    """
    Required fields to send an exposure
    """

    experiment: str
    subject: str
    variant: str
    exposed_at: datetime


class LabratClient:
    """
    Client for talking to the labrat server

    TODO - Authentication
    """

    def __init__(
        self,
        base_url: str | None = None,
        poll_interval: float = 30.0,
        queue_maxsize: int = 1000,
    ):
        base_url = base_url or os.environ.get("LABRAT_URL")
        if not base_url:
            raise ValueError("Labrat URL not set")
        self.base_url: str = base_url

        self.config: None | dict[str, dict[str, bool | list[dict[str, Any]]]] = None
        # TODO make exposure data tracking thread safe
        # TODO add TTL to _exposure_pairs to remove memory leak
        self._exposures: queue.Queue[Exposure] = queue.Queue(maxsize=queue_maxsize)
        self._exposure_pairs: set[tuple[str, str]] = set()
        self._drop_count = 0

        self._poller = Worker(self._poll, "labrat-poller")
        self._poll_interval = poll_interval

        self._sender = Worker(self._send_queued, "labrat-sender")
        self._sender.start()

    def _send_queued(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                event = self._exposures.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                self._send_exposure(event)
            except LabratConnectionError:
                logger.warning("Could not transmit exposure. Dropping.")
            except Exception:
                logger.warning("Unexpected error sending exposure", exc_info=True)

    def _ensure_started(self):
        self._poller.start(before=lambda: self._refresh(timeout=1))

    def _poll(self, stop_event: threading.Event) -> None:
        while not stop_event.wait(self._poll_interval):
            self._refresh()

    def _refresh(self, timeout: float = 5):
        try:
            self.config = self.fetch_config(timeout)
        except LabratError as e:
            logger.warning("Config refresh failed: %s", e)
        except Exception:
            logger.warning("Unexpected error during config refresh", exc_info=True)

    def _send_exposure(self, event: Exposure, *, timeout: float = 5) -> None:
        """
        Send an exposure report to the server.
        """
        payload = {
            "experiment": event.experiment,
            "subject": event.subject,
            "variant": event.variant,
            "exposed_at": event.exposed_at.isoformat(),
        }

        try:
            # TODO add retry / backoff
            r = requests.post(
                self.base_url + "/api/v1/experiment/record-exposure",
                json=payload,
                timeout=timeout,
            )
            r.raise_for_status()
        except requests.RequestException as e:
            raise LabratConnectionError(f"Could not send exposure: {e}") from e

    @staticmethod
    def parse_config(config: dict) -> dict:
        config_flags = config["flags"]

        for flag in config_flags.values():
            for experiment in flag["experiments"]:
                experiment["start_at"] = datetime.fromisoformat(experiment["start_at"])
                experiment["end_at"] = datetime.fromisoformat(experiment["end_at"])

        return config_flags

    def fetch_config(self, timeout: float = 5) -> dict:
        """
        Fetch the feature flag and experiment configuration from the server.
        Raises on failed request.

        TODO At scale: pub/sub rather than polled.
        """
        try:
            r = requests.get(self.base_url + "/config", timeout=timeout)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            raise LabratConnectionError(f"Could not fetch config: {e}") from e

        try:
            return self.parse_config(data)
        except (KeyError, ValueError, TypeError) as e:
            raise LabratConfigError(f"Could not parse config: {e}") from e

    def close(self) -> None:
        """
        Stops background polling. Calling stop multiple times is harmless.

        Calling is_flag_on() after calling close() will use the cached copy of the server config.
        :return:
        """
        self._poller.stop()
        self._sender.stop()

    def is_flag_on(self, flag_name: str, user_id: str, default: bool = False) -> bool:
        self._ensure_started()
        # In case we haven't successfully connected to the server, return the default.
        if not self.config:
            return default

        flag_result = flags.evaluate(self.config, flag_name, user_id, default=default)

        if flag_result.experiment_slug is not None and flag_result.variant is not None:
            self.record_exposure(
                experiment_slug=flag_result.experiment_slug,
                subject=user_id,
                variant=flag_result.variant,
            )
        return flag_result.enabled

    def record_exposure(self, *, experiment_slug: str, subject: str, variant: str):
        if (experiment_slug, subject) in self._exposure_pairs:
            return

        try:
            exposure = Exposure(
                experiment=experiment_slug,
                subject=subject,
                variant=variant,
                exposed_at=datetime.now(UTC),
            )
            self._exposures.put_nowait(exposure)
            self._exposure_pairs.add((experiment_slug, subject))
            if self._drop_count > 0:
                logger.warning(
                    "Exposure queue healthy again, discarded %d exposure reports.",
                    self._drop_count,
                )
                self._drop_count = 0
        except queue.Full:
            if self._drop_count == 0:
                logger.warning("Exposure queue full, dropping exposure reports.")
            self._drop_count += 1
