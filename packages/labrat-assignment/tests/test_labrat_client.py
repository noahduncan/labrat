import logging
import threading
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
import responses
from labrat_assignment.labrat_client import LabratClient

TEST_URL = "http://labrat.test"


@pytest.fixture
def client():
    c = LabratClient(TEST_URL, poll_interval=3600)
    yield c
    c.stop_polling()


@responses.activate
def test_labrat_client_init_raises_when_no_url():
    with pytest.raises(ValueError) as e:
        LabratClient(None)
    assert str(e.value) == "Labrat URL not set"


@responses.activate
def test_labrat_client_init_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("LABRAT_URL", TEST_URL)
    c = LabratClient(None)
    assert c.base_url == TEST_URL
    assert not responses.calls
    assert c._thread is None


@responses.activate
def test_labrat_client_fetch_config_not_called_for_every_operation(client):
    with patch.object(
        client,
        "fetch_config",
        return_value={"test": {"enabled": True, "experiments": []}},
    ) as fake:
        client.is_flag_on("test", "1")
        client.is_flag_on("test", "2")

    fake.assert_called_once()


@responses.activate
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


@responses.activate
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


@responses.activate
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


@responses.activate
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
    assert client._thread.is_alive()
    assert result == default_flag_state


@responses.activate
def test_labrat_client_stop_polling_ends_thread(client):
    resp = responses.Response(
        method="GET",
        url=TEST_URL + "/config",
        status=200,
        json={"flags": {"test": {"enabled": True, "experiments": []}}},
    )
    responses.add(resp)

    client._ensure_started()
    client.stop_polling()

    assert not client._thread.is_alive()

    # Cannot start the thread again after manual stop
    client._ensure_started()
    assert not client._thread.is_alive()


@responses.activate
def test_labrat_client_stop_polling_doesnt_raise_when_thread_not_started(client):
    client.stop_polling()

    assert client._thread is None


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


@responses.activate
def test_labrat_client_fetch_config_called_in_thread():
    """
    The first fetch happens synchronously in _ensure_started on this thread, so any
    later fetch can only have come from the background polling thread.

    This is maybe over designed here with the guidance of claude. We're using threading
    in order to do two things: 1. end the polling after 2+ polls and 2. end the test if it takes 1s+ to get 2+ polls.
    A call count and a timeout is probably sufficient, but this prevents brittleness on a busy server where two calls
    takes significantly longer than normal.

    If nothing else, it was an interesting exercise academically.
    """
    client = LabratClient(TEST_URL, poll_interval=0.01)
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
            client.stop_polling()

    # The poller may fetch more than once before it stops, so this is a minimum.
    assert mock_fetch.call_count >= 2
