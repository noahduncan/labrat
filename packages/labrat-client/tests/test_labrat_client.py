import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import requests
import responses
import time_machine
from labrat_client.labrat_client import Exposure, LabratClient

TEST_URL = "http://labrat.test"
EXPOSED_AT_DATETIME = datetime(2026, 10, 1, tzinfo=UTC)
EXPOSURE_DATA: Exposure = Exposure(
    experiment="test-experiment",
    subject="test_subject",
    variant="control",
    exposed_at=EXPOSED_AT_DATETIME,
)


# Ensure all tests in this file use responses so no actual HTTP requests are made.
@pytest.fixture(autouse=True)
def _mock_requests():
    with responses.mock:
        yield


@pytest.fixture
def make_client():
    clients = []

    def _make(*, sender: bool = True, **overrides: Any) -> LabratClient:
        overrides.setdefault("base_url", TEST_URL)
        overrides.setdefault("poll_interval", 3600)

        client = LabratClient(**overrides)
        if not sender:
            client._sender.stop()
        clients.append(client)
        return client

    yield _make

    for c in clients:
        c.close()


@pytest.fixture
def client(make_client):
    """
    A LabratClient instance with the common configuration for tests.
    """
    return make_client()


def wait_until(condition: Callable[[], object], timeout: float = 1) -> bool:
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return bool(condition())


def test_labrat_client_init_raises_when_no_url(make_client):
    with pytest.raises(ValueError) as e:
        make_client(base_url=None)
    assert str(e.value) == "Labrat URL not set"


def test_labrat_client_init_falls_back_to_env_var(make_client, monkeypatch):
    monkeypatch.setenv("LABRAT_URL", TEST_URL)
    c = make_client(base_url=None)
    assert c.base_url == TEST_URL
    assert not responses.calls
    assert c._poller._thread is None


def test_labrat_client_fetch_config_not_called_for_every_operation(client):
    with patch.object(
        client,
        "fetch_config",
        return_value={"test": {"enabled": True, "experiments": []}},
    ) as fake:
        client.is_flag_on("test", "1")
        client.is_flag_on("test", "2")

    fake.assert_called_once()


def test_labrat_client_warns_on_500_from_server(client, caplog):
    caplog.set_level(logging.WARNING)

    resp = responses.Response(
        method="GET",
        url=TEST_URL + "/config",
        status=500,
        body="Internal Server Error",
    )
    responses.add(resp)

    client.config = {"test": {"enabled": True, "experiments": []}}

    client._refresh()

    assert "Internal Server Error" in caplog.text
    assert client.config == {"test": {"enabled": True, "experiments": []}}


def test_labrat_client_warns_on_malformed_response(client, caplog):
    caplog.set_level(logging.WARNING)

    resp = responses.Response(
        method="GET",
        url=TEST_URL + "/config",
        status=200,
        json={"something": "unexpected"},
    )
    responses.add(resp)

    client.config = {"test": {"enabled": True, "experiments": []}}

    client._refresh()

    assert "Could not parse config" in caplog.text
    assert client.config == {"test": {"enabled": True, "experiments": []}}


def test_labrat_client__refresh_sets_config(client):
    resp = responses.Response(
        method="GET",
        url=TEST_URL + "/config",
        json={"flags": {"test": {"enabled": True, "experiments": []}}},
        status=200,
    )
    responses.add(resp)
    client._refresh()

    assert client.config == {"test": {"enabled": True, "experiments": []}}


def test_labrat_client_is_flag_on_returns_default_on_fetch_config_failure(client):
    resp = responses.Response(
        method="GET",
        url=TEST_URL + "/config",
        status=500,
        body="Internal Server Error",
    )
    responses.add(resp)
    default_flag_state = True
    result = client.is_flag_on("test", "1", default_flag_state)
    assert client._poller.is_alive()
    assert result == default_flag_state


def test_labrat_client_parse_config_converts_isodatetime_stamps(client):
    flags = client.parse_config(
        {
            "flags": {
                "test": {
                    "enabled": True,
                    "experiments": [
                        {
                            "start_at": "2026-08-09T10:20:30Z",
                            "end_at": "2026-08-10T10:20:30Z",
                        }
                    ],
                }
            }
        }
    )

    assert flags["test"]["experiments"][0]["start_at"] == datetime(
        2026, 8, 9, 10, 20, 30, tzinfo=UTC
    )
    assert flags["test"]["experiments"][0]["end_at"] == datetime(
        2026, 8, 10, 10, 20, 30, tzinfo=UTC
    )


def test_labrat_client_fetch_config_called_in_thread(make_client):
    """
    The first fetch happens synchronously in _ensure_started on this thread, so any
    later fetch can only have come from the background polling thread.
    """
    client = make_client(poll_interval=0.01)

    with patch.object(client, "fetch_config", return_value={}) as mock_fetch:
        try:
            client.is_flag_on("test", "1")
            # The poller may fetch more than once before it stops, so this is a minimum.
            assert wait_until(lambda: mock_fetch.call_count >= 2)
        finally:
            # Stop before the patch is removed so the thread never calls the real
            # fetch_config.
            client.close()


def test_labrat_client_records_exposure_when_active_experiment(make_client):
    client = make_client(sender=False)
    client.config = {
        "test": {
            "enabled": True,
            "experiments": [
                {
                    "slug": "test_experiment",
                    "start_at": datetime.now(UTC) - timedelta(days=1),
                    "end_at": datetime.now(UTC) + timedelta(days=1),
                    "control": 50,
                }
            ],
        }
    }

    client.is_flag_on("test", "1")
    assert client._exposures.qsize() == 1
    assert client._exposures.get_nowait().experiment == "test_experiment"


def test_labrat_client_does_not_record_exposure_when_no_active_experiment(make_client):
    client = make_client(sender=False)
    client.config = {
        "test": {
            "enabled": True,
            "experiments": [
                {
                    "slug": "test_experiment",
                    "start_at": datetime.now(UTC) + timedelta(days=1),
                    "end_at": datetime.now(UTC) + timedelta(days=3),
                    "control": 50,
                }
            ],
        }
    }

    client.is_flag_on("test", "1")
    assert client._exposures.qsize() == 0


def test_labrat_client_is_flag_on_only_adds_one_exposure_per_experiment_subject_pair(
    make_client,
):
    client = make_client(sender=False)
    client.config = {
        "test": {
            "enabled": True,
            "experiments": [
                {
                    "slug": "test_experiment",
                    "start_at": datetime.now(UTC) - timedelta(days=1),
                    "end_at": datetime.now(UTC) + timedelta(days=3),
                    "control": 50,
                },
            ],
        },
        "test2": {
            "enabled": True,
            "experiments": [
                {
                    "slug": "test_experiment2",
                    "start_at": datetime.now(UTC) - timedelta(days=1),
                    "end_at": datetime.now(UTC) + timedelta(days=3),
                    "control": 50,
                },
            ],
        },
    }

    client.is_flag_on("test", "1")
    client.is_flag_on("test", "1")
    assert len(client._exposure_pairs) == 1
    assert client._exposures.qsize() == 1

    client.is_flag_on("test2", "1")
    client.is_flag_on("test2", "1")
    assert len(client._exposure_pairs) == 2
    assert client._exposures.qsize() == 2


def test_labrat_client_queue_overrun_logging(make_client, caplog):
    caplog.set_level(logging.WARNING)
    client = make_client(sender=False, queue_maxsize=1)
    client.config = {
        "test": {
            "enabled": True,
            "experiments": [
                {
                    "slug": "test_experiment",
                    "start_at": datetime.now(UTC) - timedelta(days=1),
                    "end_at": datetime.now(UTC) + timedelta(days=3),
                    "control": 50,
                },
            ],
        },
        "test2": {
            "enabled": True,
            "experiments": [
                {
                    "slug": "test_experiment2",
                    "start_at": datetime.now(UTC) - timedelta(days=1),
                    "end_at": datetime.now(UTC) + timedelta(days=3),
                    "control": 50,
                },
            ],
        },
    }

    client.is_flag_on("test", "1")
    client.is_flag_on("test2", "1")
    client.is_flag_on("test2", "1")

    assert client._exposures.qsize() == 1
    assert len(client._exposure_pairs) == 1
    assert client._drop_count == 2
    assert caplog.text.count("Exposure queue full, dropping exposure reports.") == 1

    client._exposures.get_nowait()

    client.is_flag_on("test2", "1")
    assert client._drop_count == 0
    assert len(client._exposure_pairs) == 2
    assert ("test_experiment2", "1") in client._exposure_pairs
    assert (
        caplog.text.count("Exposure queue healthy again, discarded 2 exposure reports.")
        == 1
    )


@time_machine.travel(EXPOSED_AT_DATETIME)
def test_labrat_client_record_exposure_queues_exposure(make_client):
    client = make_client(sender=False)
    client.record_exposure(
        experiment_slug=EXPOSURE_DATA.experiment,
        subject=EXPOSURE_DATA.subject,
        variant=EXPOSURE_DATA.variant,
    )

    assert client._exposures.qsize() == 1
    assert client._exposures.get_nowait() == EXPOSURE_DATA


def test_labrat_client_sender_posts_queued_exposure(client, caplog):
    caplog.set_level(logging.WARNING)
    responses.post(url=TEST_URL + "/api/v1/experiment/record-exposure", status=200)
    client._exposures.put(EXPOSURE_DATA)

    assert wait_until(lambda: responses.calls)
    client._sender.stop()

    assert len(responses.calls) == 1
    assert caplog.text == ""

    request_body = responses.calls[0].request.body
    assert request_body is not None
    assert json.loads(request_body) == {
        "experiment": EXPOSURE_DATA.experiment,
        "subject": EXPOSURE_DATA.subject,
        "variant": EXPOSURE_DATA.variant,
        "exposed_at": EXPOSURE_DATA.exposed_at.isoformat(),
    }


def test_labrat_client_record_exposure_connection_error_logs_warning(client, caplog):
    caplog.set_level(logging.WARNING)
    responses.post(
        url=TEST_URL + "/api/v1/experiment/record-exposure",
        body=requests.RequestException("Something happened"),
    )
    client.record_exposure(
        experiment_slug=EXPOSURE_DATA.experiment,
        subject=EXPOSURE_DATA.subject,
        variant=EXPOSURE_DATA.variant,
    )

    wait_until(lambda: "Could not transmit" in caplog.text)

    assert "Could not transmit" in caplog.text


def test_labrat_client_record_exposure_exception_logs_warning_and_thread_survives(
    client, caplog
):
    caplog.set_level(logging.WARNING)
    with patch.object(
        client, "_send_exposure", side_effect=[Exception("boom"), None]
    ) as cm:
        client.record_exposure(
            experiment_slug=EXPOSURE_DATA.experiment,
            subject=EXPOSURE_DATA.subject,
            variant=EXPOSURE_DATA.variant,
        )
        client.record_exposure(
            experiment_slug=EXPOSURE_DATA.experiment + "1",
            subject=EXPOSURE_DATA.subject,
            variant=EXPOSURE_DATA.variant,
        )

        # Two calls means that the thread survived the first failure.
        assert wait_until(lambda: cm.call_count == 2)
        assert caplog.text.count("Unexpected error sending exposure") == 1
