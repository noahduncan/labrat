import threading

from labrat_client.worker import Worker


def wait_until_stopped(stop_event: threading.Event) -> None:
    stop_event.wait()


def test_worker_stop_ends_thread():
    worker = Worker(wait_until_stopped, "test-worker")

    worker.start()
    assert worker.is_alive()

    worker.stop()
    assert not worker.is_alive()

    # Cannot start the thread again after manual stop
    worker.start()
    assert not worker.is_alive()


def test_worker_stop_doesnt_raise_when_thread_not_started():
    worker = Worker(wait_until_stopped, "test-worker")

    worker.stop()

    assert worker._thread is None
