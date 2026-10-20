from labrat_client.bucketing import bucket_for
from pytest import mark

EXPECTED_BUCKETS = [
    ("experiment_slug", 1, 25),
    ("experiment_slug-green", 1, 52),
    ("experiment_slug", 2, 1),
]


@mark.parametrize(("experiment_slug", "user_id", "expected_bucket"), EXPECTED_BUCKETS)
def test_bucket_for_is_deterministic(
    experiment_slug: str, user_id: int, expected_bucket: int
):
    assert bucket_for(experiment_slug, str(user_id)) == expected_bucket


def test_bucket_for_changes_bucket_for_different_inputs():
    assert bucket_for("experiment_slug", "1") != bucket_for(
        "experiment_slug-green", "1"
    )
    assert bucket_for("experiment_slug", "1") != bucket_for("experiment_slug", "2")


def test_bucket_for_result_is_in_range():
    assert all(0 <= bucket_for("experiment_slug", str(u)) < 100 for u in range(10_000))
