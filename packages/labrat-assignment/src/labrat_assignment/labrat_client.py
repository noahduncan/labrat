import logging
import os
import threading
from datetime import datetime

import requests

from labrat_assignment import flags
from labrat_assignment.exceptions import (
    LabratConfigError,
    LabratConnectionError,
    LabratError,
)

logger = logging.getLogger(__name__)


class LabratClient:
    """
    Client for talking to the labrat server

    TODO - Authentication
    """

    def __init__(self, base_url: str | None = None, poll_interval: float = 30.0):
        self.base_url = base_url or os.environ.get("LABRAT_URL")
        if not self.base_url:
            raise ValueError("Labrat URL not set")

        self.config = None

        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None

    def _ensure_started(self):
        # optimize- if the thread is running, skip getting a lock: no risk of starting multiple threads.
        if self._thread is not None and self._thread.is_alive():
            return
        with self._lock:
            # Double check that the thread didn't start running while we obtained a lock
            if self._thread is not None and self._thread.is_alive():
                return
            # Don't start polling if polling was manually stopped.
            if self._stop.is_set():
                return
            # poll now and initiate a thread to poll in the background
            self._refresh(timeout=1)
            self._thread = threading.Thread(target=self._poll, daemon=True)
            self._thread.start()

    def stop_polling(self):
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join()

    def _poll(self):
        while not self._stop.wait(self._poll_interval):
            self._refresh()

    def _refresh(self, timeout: float = 5):
        try:
            self.config = self.fetch_config(timeout)
        except LabratError as e:
            logger.warning("Config refresh failed: %s", e)
        except Exception:
            logger.warning("Unexpected error during config refresh", exc_info=True)

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
            return self.parse_config(r.json())
        except requests.RequestException as e:
            raise LabratConnectionError(f"Could not fetch config: {e}") from e
        except (KeyError, ValueError, TypeError) as e:
            raise LabratConfigError(f"Could not parse config: {e}") from e

    def is_flag_on(self, flag_name: str, user_id: str, default: bool = False) -> bool:
        self._ensure_started()
        # In case we haven't successfully connected to the server, return the default.
        if not self.config:
            return default

        flag_result = flags.evaluate(self.config, flag_name, user_id, default=default)
        return flag_result.enabled
