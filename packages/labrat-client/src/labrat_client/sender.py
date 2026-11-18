import logging
import queue
import threading
import time
from collections.abc import Callable

from labrat_client.worker import Worker

logger = logging.getLogger(__name__)


class Sender:
    """A helper class that calls a function for each enqueued item.

    Args:
        send_function: A function to call on each queued item to send it externally.
            Exceptions raised will be logged and swallowed.
        maxsize: The maximum size of the queue.
        name: The name of the Sender.
    """

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
        """Enqueues an item to the queue.

        Args:
            item: The item to enqueue.

        Raises:
            queue.Full: If the queue is full.
        """
        self._queue.put_nowait(item)

    def start(self) -> None:
        """Starts the sender (thread safe)."""
        self._worker.start()

    def stop(self, timeout: float) -> None:
        """Stops the sender, waiting for `timeout` (s) for the queue to drain.

        Args:
            timeout: A soft timeout in seconds to wait for the queue to drain.
                If timeout expires before the queue has drained, unsent items
                will be dropped, and a warning will be created.
        """
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
