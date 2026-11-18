import threading
from collections.abc import Callable


class Worker:
    """A daemon that performs a repetitive task in a separate thread.

    Args:
        target: A function that watches the passed event and returns promptly once set.
        name: The name of the worker.
    """

    def __init__(self, target: Callable[[threading.Event], None], name: str):
        self._target = target
        self._name = name
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def start(self, before: Callable[[], None] | None = None) -> None:
        """Starts the worker.

        Thread safe and is safe to be called multiple times.

        Args:
            before: Runs at most once, synchronously, in the calling thread.
        """
        # optimize- if the thread is running, skip getting a lock
        if self.is_alive() or self._stop.is_set():
            return
        with self._lock:
            # Double check that the thread didn't start running while we obtained a lock
            if self.is_alive():
                return
            # Don't initialize thread if worker was manually stopped.
            if self._stop.is_set():
                return
            if before is not None:
                before()
            self._thread = threading.Thread(
                target=self._target, args=(self._stop,), daemon=True, name=self._name
            )
            self._thread.start()

    def stop(self) -> None:
        """Tells the worker to stop and waits for it to finish."""
        self._stop.set()
        if self._thread is not None and self.is_alive():
            self._thread.join()

    def is_alive(self) -> bool:
        """Returns whether the worker is alive."""
        return self._thread is not None and self._thread.is_alive()
