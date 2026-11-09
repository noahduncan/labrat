import logging
import queue
import threading
import time
from collections.abc import Callable

from labrat_client.worker import Worker

logger = logging.getLogger(__name__)


class Sender:
    def __init__(self, send_function: Callable, maxsize: int, name: str) -> None:
        self.name = name
        self._queue = queue.Queue(maxsize=maxsize)
        self._send_function = send_function
        self._worker = Worker(self._send_queued, name)

    def _send_queued(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                self._send_function(item)
            except Exception:
                logger.exception(
                    "Unhandled exception raised sending item from %s", self.name
                )

    def enqueue(self, item) -> None:
        self._queue.put_nowait(item)

    def start(self) -> None:
        self._worker.start()

    def stop(self, timeout) -> None:
        close_deadline = time.monotonic() + timeout
        while (
            self._worker.is_alive()
            and self._queue.qsize() > 0
            and time.monotonic() < close_deadline
        ):
            time.sleep(0.1)

        self._worker.stop()

        if self._queue.qsize() > 0:
            logger.warning(
                "Queue did not flush within %s seconds, dropping %d item(s).",
                timeout,
                self._queue.qsize(),
            )
