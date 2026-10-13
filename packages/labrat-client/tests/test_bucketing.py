from labrat_client.bucketing import bucket_for
from pytest import mark

EXPECTED_BUCKETS = [
    ("experiment_slug", 1, 25),
    ("experiment_slug-green", 1, 52),
    ("experiment_slug", 2, 1),
]


@mark.parametrize(("flag_name", "user_id", "expected_bucket"), EXPECTED_BUCKETS)
def test_bucket_for_is_deterministic(
    flag_name: str, user_id: int, expected_bucket: int
):
    assert bucket_for(flag_name, user_id) == expected_bucket


def test_bucket_for_changes_bucket_for_different_inputs():
    assert bucket_for("experiment_slug", 1) != bucket_for("experiment_slug-green", 1)
    assert bucket_for("experiment_slug", 1) != bucket_for("experiment_slug", 2)


def test_bucket_for_result_is_in_range():
    assert all(0 <= bucket_for("experiment_slug", u) < 100 for u in range(10_000))
