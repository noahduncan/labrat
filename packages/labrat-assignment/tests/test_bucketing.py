from labrat_assignment.bucketing import bucket_for
from pytest import mark

EXPECTED_BUCKETS = [("feature flag", 1, 14), ("feature flag-green", 1, 77), ("feature flag", 2, 89)]

@mark.parametrize(("flag_name", "user_id", "expected_bucket"), EXPECTED_BUCKETS)
def test_bucket_for_is_deterministic(flag_name: str, user_id: int, expected_bucket: int):
    assert bucket_for(flag_name, user_id) == expected_bucket

def test_bucket_for_changes_bucket_for_different_inputs():
    assert bucket_for("feature flag", 1) != bucket_for("feature flag-green", 1)
    assert bucket_for("feature flag", 1) != bucket_for("feature flag", 2)

def test_bucket_for_result_is_in_range():
    assert all(0 <= bucket_for("flag", u) < 100 for u in range(10_000))
