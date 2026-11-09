import logging
import queue
import threading
import time

import pytest
from labrat_client.sender import Sender


@pytest.fixture
def make_sender():
    senders = []

    def _make(send_function, maxsize: int = 10) -> Sender:
        sender = Sender(send_function, maxsize, "test-sender")
        senders.append(sender)
        return sender

    yield _make

    for s in senders:
        s.stop(timeout=2)


def test_sender_sends_enqueued_items(make_sender):
    calls = []
    sender = make_sender(calls.append)
    sender.start()

    sender.enqueue("item 1")
    sender.enqueue("item 2")
    sender.stop(timeout=2)

    assert calls == ["item 1", "item 2"]


def test_sender_survives_send_function_exception(make_sender, caplog):
    caplog.set_level(logging.WARNING)
    calls = []

    def send_fn(item: str):
        calls.append(item)
        if item == "item 1":
            raise RuntimeError("boom")

    sender = make_sender(send_fn)
    sender.start()

    sender.enqueue("item 1")
    sender.enqueue("item 2")
    sender.stop(timeout=2)

    # Item 2 being sent means the thread survived item 1's exception.
    assert calls == ["item 1", "item 2"]
    assert (
        caplog.text.count("Unhandled exception raised sending item from test-sender")
        == 1
    )
    assert "boom" in caplog.text


def test_sender_enqueue_raises_when_full(make_sender):
    sender = make_sender(lambda _: None, maxsize=1)

    sender.enqueue("item 1")

    with pytest.raises(queue.Full):
        sender.enqueue("item 2")


def test_sender_stop_flushes_remaining_queued_items(make_sender):
    calls = []

    def send_fn(item: str):
        calls.append(item)
        time.sleep(0.05)

    sender = make_sender(send_fn)
    sender.start()

    sender.enqueue("item 1")
    sender.enqueue("item 2")
    sender.stop(timeout=2)

    assert calls == ["item 1", "item 2"]


def test_sender_stop_warns_if_queue_times_out(make_sender, caplog):
    caplog.set_level(logging.WARNING)
    timeout = 0.1
    first_send_started = threading.Event()

    def send_fn(_):
        first_send_started.set()
        time.sleep(0.2)

    sender = make_sender(send_fn)
    sender.start()

    sender.enqueue("item 1")
    sender.enqueue("item 2")
    # Item 1 is in flight, item 2 is still queued.
    assert first_send_started.wait(timeout=1)

    sender.stop(timeout=timeout)

    assert (
        f"Queue did not flush within {timeout} seconds, dropping 1 item(s)."
        in caplog.text
    )


def test_sender_stop_is_harmless_when_never_started(make_sender, caplog):
    caplog.set_level(logging.WARNING)
    sender = make_sender(lambda _: None)

    sender.stop(timeout=0.1)

    assert caplog.text == ""
