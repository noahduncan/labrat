import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import responses
from labrat_client.labrat_client import LabratClient

TEST_URL = "http://labrat.test"


# Ensure all tests in this file use responses so no actual HTTP requests are made.
@pytest.fixture(autouse=True)
def _mock_requests():
    with responses.mock:
        yield


@pytest.fixture
def make_client():
    clients = []

    def _make(**overrides: Any) -> LabratClient:
        overrides.setdefault("base_url", TEST_URL)
        overrides.setdefault("poll_interval", 3600)

        client = LabratClient(**overrides)
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

    This is maybe over designed here with the guidance of claude. We're using threading
    in order to do two things: 1. end the polling after 2+ polls and 2. end the test if it takes 1s+ to get 2+ polls.
    A call count and a timeout is probably sufficient, but this prevents brittleness on a busy server where two calls
    takes significantly longer than normal.

    If nothing else, it was an interesting exercise academically.
    """
    client = make_client(poll_interval=0.01)
    fetched_twice = threading.Event()
    fetch_count = 0

    def fake_fetch(*args, **kwargs):
        nonlocal fetch_count
        fetch_count += 1
        if fetch_count >= 2:
            # Signal the waiting test thread that the poller has fetched.
            fetched_twice.set()
        return {"test": {"enabled": True, "experiments": []}}

    with patch.object(client, "fetch_config", side_effect=fake_fetch) as mock_fetch:
        try:
            client.is_flag_on("test", "1")
            # Block until the poller fetches, failing if it hasn't within a second.
            assert fetched_twice.wait(timeout=1)
        finally:
            # Stop before the patch is removed so the thread never calls the real
            # fetch_config.
            client.close()

    # The poller may fetch more than once before it stops, so this is a minimum.
    assert mock_fetch.call_count >= 2


def test_labrat_client_records_exposure_when_active_experiment(client):
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
    assert client._exposures.get_nowait()["experiment"] == "test_experiment"


def test_labrat_client_does_not_record_exposure_when_no_active_experiment(client):
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
    client,
):
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
    client = make_client(queue_maxsize=1)
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
