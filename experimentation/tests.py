from datetime import UTC, datetime, timedelta
from itertools import count

from django.core.exceptions import ValidationError
from django.test.testcases import TestCase
from django.utils import timezone

from .models import Experiment, FeatureFlag
from .services.config import snapshot

_counter = count(1)

def make_experiment(**overrides):
    now = timezone.now()
    fields = {
        "name": "test experiment" + str(next(_counter)),
        "prediction": "The future",
        "start_at": now,
        "end_at": now + timedelta(days=1),
        "split_a": 40,
        "split_b": 60,
        **overrides,
    }
    if "feature_flag" not in fields:
        fields["feature_flag"] = FeatureFlag.objects.create(name="test feature flag" + str(next(_counter)))

    return Experiment.objects.create(**fields)

class ConfigTest(TestCase):
    def setUp(self):
        self.feature_flag = FeatureFlag.objects.create(name="test flag")
        self.now = datetime(2026, 10, 8, 0, tzinfo=UTC)

    def test_config_flag_with_no_experiments(self):
        self.assertEqual(snapshot(self.now), {"flags": {"test flag": {"enabled": False, "experiments": []}}})

    def test_config_flag_with_ended_experiment(self):
        make_experiment(
            start_at=self.now - timedelta(days=4),
            end_at=self.now - timedelta(days=1),
            feature_flag=self.feature_flag,
        )

        self.assertEqual(len(snapshot(self.now)["flags"]["test flag"]["experiments"]), 0)

    def test_config_flag_with_unended_experiment(self):
        make_experiment(
            name="test experiment",
            start_at=self.now - timedelta(days=4),
            end_at=self.now + timedelta(days=3),
            feature_flag=self.feature_flag,
        )

        self.assertIn("test-experiment", [e["slug"] for e in snapshot(self.now)["flags"]["test flag"]["experiments"]])

    def test_config_payload_structure(self):
        make_experiment(
            name="test experiment",
            start_at=self.now - timedelta(days=1),
            end_at=self.now + timedelta(days=1),
            feature_flag=self.feature_flag,
            prediction="The future",
            split_a=40,
            split_b=60,
        )

        self.assertEqual(
            snapshot(self.now),
            {
                "flags": {
                    "test flag": {
                        "enabled": False,
                        "experiments": [
                            {
                                "name": "test experiment",
                                "slug": "test-experiment",
                                "split_a": 40,
                                "split_b": 60,
                                "start_at": self.now - timedelta(days=1),
                                "end_at": self.now + timedelta(days=1),
                            }
                        ],
                    }
                }
            },
        )

    def test_config_flag_with_future_experiment(self):
        make_experiment(
            name="test experiment",
            start_at=self.now + timedelta(days=2),
            end_at=self.now + timedelta(days=3),
            feature_flag=self.feature_flag,
        )

        self.assertIn("test-experiment", [e["slug"] for e in snapshot(self.now)["flags"]["test flag"]["experiments"]])

    def test_config_flag_experiment_ending_now_not_included(self):
        make_experiment(
            name="test experiment",
            start_at=self.now - timedelta(days=2),
            end_at=self.now,
            feature_flag=self.feature_flag,
        )

        self.assertNotIn("test-experiment", [e["slug"] for e in snapshot(self.now)["flags"]["test flag"]["experiments"]])


class ExperimentTest(TestCase):
    def setUp(self):
        self.feature_flag = FeatureFlag.objects.create(name="test feature flag")
        self.now = timezone.now()

    def test_experiment_generates_slug(self):
        experiment = make_experiment(
            name="test experiment",
        )
        self.assertEqual(experiment.slug, "test-experiment")

    def test_experiment_resaving_does_not_error(self):
        e = make_experiment(name="test experiment")
        e.name = "super test experiment"
        e.save()
        self.assertEqual(e.slug, "test-experiment")

    def test_experiment_cannot_overlap_another_fully_within(self):
        make_experiment(
            start_at=self.now,
            end_at=self.now + timedelta(days=3),
            feature_flag=self.feature_flag,
        )
        with self.assertRaises(ValidationError):
            make_experiment(
                start_at=self.now + timedelta(days=1),
                end_at=self.now + timedelta(days=2),
                feature_flag=self.feature_flag,
            )

    def test_experiments_with_different_flags_can_overlap_dates(self):
        FeatureFlag.objects.create(name="secondary test_flag")

        make_experiment(
            start_at=self.now,
            end_at=self.now + timedelta(days=3),
        )
        make_experiment(
            start_at=self.now + timedelta(days=1),
            end_at=self.now + timedelta(days=2),
        )

        self.assertEqual(Experiment.objects.count(), 2)

    def test_experiment_cannot_overlap_another_partial(self):
        make_experiment(
            start_at=self.now,
            end_at=self.now + timedelta(days=2),
            feature_flag=self.feature_flag,
        )
        with self.assertRaises(ValidationError):
            make_experiment(
                start_at=self.now + timedelta(days=1),
                end_at=self.now + timedelta(days=2),
                feature_flag=self.feature_flag,
            )

    def test_experiment_can_abut_times(self):
        abutting_time = self.now + timedelta(days=2)
        make_experiment(
            start_at=self.now,
            end_at=abutting_time,
            feature_flag=self.feature_flag,
        )
        make_experiment(
            start_at=abutting_time,
            end_at=abutting_time + timedelta(days=1),
            feature_flag=self.feature_flag,
        )

        self.assertEqual(Experiment.objects.count(), 2)

    def test_experiment_error_if_splits_do_not_sum_to_100(self):
        with self.assertRaises(ValidationError) as cm:
            make_experiment(
                split_a=40,
                split_b=40,
            )

        self.assertTrue("must sum to 100" in cm.exception.messages[0])

    def test_experiment_error_if_split_a_lte_0(self):
        with self.assertRaises(ValidationError) as cm:
            make_experiment(
                split_a=-10,
                split_b=110,
            )

        self.assertTrue("'split_a' must be greater than 0" in cm.exception.messages[0])

    def test_experiment_error_if_split_b_lte_0(self):
        with self.assertRaises(ValidationError) as cm:
            make_experiment(
                split_a=110,
                split_b=-10,
            )

        self.assertTrue("'split_b' must be greater than 0" in cm.exception.messages[0])

