from datetime import UTC, datetime, timedelta

import pytest
from labrat_client.bucketing import bucket_for
from labrat_client.exceptions import LabratWarning
from labrat_client.flags import FlagResult, evaluate

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)

# Known buckets for the slug "experiment" (asserted in test_known_buckets).
TREATMENT_USER = "1"  # bucket 96
CONTROL_USER = "268"  # bucket 10
BOUNDARY_USER = "148"  # bucket 50


def create_flag_dict(flag_name: str, enabled: bool, experiments: list) -> dict:
    """
    The server returns flags under a root key of "flags", but that is stripped out in
    the client. We skip it here too as this emulates what the client would request.
    """
    return {
        flag_name: {
            "enabled": enabled,
            "experiments": experiments,
        }
    }


def create_experiment(
    slug: str = "experiment",
    control: int = 50,
    start_at: datetime = NOW - timedelta(days=1),
    end_at: datetime = NOW + timedelta(days=1),
) -> dict:
    return {
        "slug": slug,
        "control": control,
        "treatment": 100 - control,
        "start_at": start_at,
        "end_at": end_at,
    }


def assert_result(
    result: FlagResult, enabled: bool, experiment_slug: str | None, variant: str | None
):
    assert result.enabled == enabled
    assert result.experiment_slug == experiment_slug
    assert result.variant == variant


def test_known_buckets():
    """Guards the user constants above; if bucketing changes, update them."""
    assert bucket_for("experiment", TREATMENT_USER) == 96
    assert bucket_for("experiment", CONTROL_USER) == 10
    assert bucket_for("experiment", BOUNDARY_USER) == 50


@pytest.mark.parametrize("flag_enabled", [False, True])
def test_evaluate_active_experiment_treatment_group_returns_not_flag_enabled(
    flag_enabled: bool,
):
    flags = create_flag_dict("flag", flag_enabled, [create_experiment()])

    result = evaluate(flags, "flag", TREATMENT_USER, NOW)

    assert_result(result, not flag_enabled, "experiment", "treatment")


@pytest.mark.parametrize("flag_enabled", [False, True])
def test_evaluate_active_experiment_control_group_returns_flag_enabled(
    flag_enabled: bool,
):
    flags = create_flag_dict("flag", flag_enabled, [create_experiment()])

    result = evaluate(flags, "flag", CONTROL_USER, NOW)

    assert_result(result, flag_enabled, "experiment", "control")


def test_evaluate_bucket_equal_to_control_is_treatment():
    """Control is buckets [0, control), so bucket == control is the first B bucket."""
    flags = create_flag_dict("flag", False, [create_experiment(control=50)])

    result = evaluate(flags, "flag", BOUNDARY_USER, NOW)

    assert result.variant == "treatment"


@pytest.mark.parametrize(
    ("control", "expected_variant"), [(0, "treatment"), (100, "control")]
)
def test_evaluate_extreme_splits_put_everyone_in_one_variant(
    control: int, expected_variant: str
):
    flags = create_flag_dict("flag", False, [create_experiment(control=control)])

    variants = {evaluate(flags, "flag", str(u), NOW).variant for u in range(1000)}

    assert variants == {expected_variant}


@pytest.mark.parametrize("flag_enabled", [False, True])
def test_evaluate_no_experiments_returns_flag_enabled_state(flag_enabled: bool):
    flags = create_flag_dict("flag", flag_enabled, [])

    result = evaluate(flags, "flag", TREATMENT_USER, NOW)

    assert_result(result, flag_enabled, None, None)


@pytest.mark.parametrize("flag_enabled", [False, True])
def test_evaluate_future_experiment_returns_flag_enabled_state(flag_enabled: bool):
    experiment = create_experiment(
        start_at=NOW + timedelta(days=1), end_at=NOW + timedelta(days=2)
    )
    flags = create_flag_dict("flag", flag_enabled, [experiment])

    result = evaluate(flags, "flag", TREATMENT_USER, NOW)

    assert_result(result, flag_enabled, None, None)


@pytest.mark.parametrize("flag_enabled", [False, True])
def test_evaluate_ended_experiment_returns_flag_enabled_state(flag_enabled: bool):
    experiment = create_experiment(
        start_at=NOW - timedelta(days=2), end_at=NOW - timedelta(days=1)
    )
    flags = create_flag_dict("flag", flag_enabled, [experiment])

    result = evaluate(flags, "flag", TREATMENT_USER, NOW)

    assert_result(result, flag_enabled, None, None)


def test_evaluate_experiment_starting_now_is_active():
    experiment = create_experiment(start_at=NOW, end_at=NOW + timedelta(days=1))
    flags = create_flag_dict("flag", False, [experiment])

    result = evaluate(flags, "flag", TREATMENT_USER, NOW)

    assert result.experiment_slug == "experiment"


def test_evaluate_experiment_ending_now_is_not_active():
    experiment = create_experiment(start_at=NOW - timedelta(days=1), end_at=NOW)
    flags = create_flag_dict("flag", False, [experiment])

    result = evaluate(flags, "flag", TREATMENT_USER, NOW)

    assert_result(result, False, None, None)


def test_evaluate_skips_ended_experiment_in_stale_config():
    """A cached config can still list an ended experiment before the active one."""
    ended = create_experiment(
        slug="ended", start_at=NOW - timedelta(days=2), end_at=NOW - timedelta(days=1)
    )
    active = create_experiment(
        slug="experiment",
        start_at=NOW - timedelta(days=1),
        end_at=NOW + timedelta(days=1),
    )
    flags = create_flag_dict("flag", False, [ended, active])

    result = evaluate(flags, "flag", TREATMENT_USER, NOW)

    assert_result(result, True, "experiment", "treatment")


def test_evaluate_no_flag_emits_warning_and_returns_default():
    flags = create_flag_dict("flag", False, [])

    with pytest.warns(LabratWarning, match=r"Flag flag_not_present is not configured"):
        result = evaluate(flags, "flag_not_present", TREATMENT_USER, NOW, default=True)

    assert_result(result, True, None, None)
