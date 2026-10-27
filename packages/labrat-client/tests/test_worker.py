import threading
import time
from unittest.mock import Mock

from labrat_client.worker import Worker


def wait_until_stopped(stop_event: threading.Event) -> None:
    stop_event.wait()


def test_worker_stop_before_start_doesnt_raise():
    worker = Worker(wait_until_stopped, "test-worker")

    worker.stop()

    assert worker._thread is None


def test_worker_start_calls_target_with_stop_event():
    target = Mock()
    worker = Worker(target, "test-worker")

    worker.start()
    worker.stop()

    target.assert_called_once_with(worker._stop)


def test_worker_before_runs_before_target():
    calls = []
    worker = Worker(lambda stop_event: calls.append("target"), "test-worker")

    worker.start(before=lambda: calls.append("before"))
    worker.stop()

    assert calls == ["before", "target"]


def test_worker_concurrent_starts_call_before_once():
    num_threads = 3
    barrier = threading.Barrier(num_threads)
    worker = Worker(wait_until_stopped, "test-worker")
    before_calls = []

    def slow_before():
        before_calls.append(1)
        time.sleep(0.05)

    def barrier_start():
        barrier.wait(timeout=1)
        worker.start(before=slow_before)

    try:
        threads = [threading.Thread(target=barrier_start) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=1)
            assert not t.is_alive()
    finally:
        worker.stop()

    assert len(before_calls) == 1


def test_worker_thread_uses_given_name():
    worker = Worker(wait_until_stopped, "test-worker")
    try:
        worker.start()

        assert worker._thread is not None
        assert worker._thread.name == "test-worker"
    finally:
        worker.stop()


def test_worker_stop_sets_event_and_waits_for_thread():
    def slow_to_exit(stop_event: threading.Event):
        stop_event.wait()
        time.sleep(0.05)

    worker = Worker(slow_to_exit, "test-worker")
    worker.start()

    assert worker.is_alive()
    assert not worker._stop.is_set()
    worker.stop()

    assert not worker.is_alive()
    assert worker._stop.is_set()


def test_worker_start_after_stop_does_nothing():
    before_calls = []
    target_calls = []

    def logging_before():
        before_calls.append(1)

    def logging_target(stop_event: threading.Event):
        target_calls.append(1)

    worker = Worker(logging_target, "test-worker")

    worker.start(before=logging_before)
    worker.stop()

    assert len(before_calls) == 1
    assert len(target_calls) == 1

    worker.start(before=logging_before)
    worker.stop()

    assert len(before_calls) == 1
    assert len(target_calls) == 1
