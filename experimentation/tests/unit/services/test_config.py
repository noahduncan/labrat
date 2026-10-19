from datetime import UTC, datetime, timedelta

import time_machine
from django.test.testcases import TestCase

from experimentation.models import FeatureFlag
from experimentation.services.config import snapshot
from experimentation.tests.unit.models.test_experiment import make_experiment

SETUP_TIME = datetime(2026, 10, 1, tzinfo=UTC)


@time_machine.travel(SETUP_TIME, tick=False)
class ConfigTest(TestCase):
    def setUp(self):
        self.feature_flag = FeatureFlag.objects.create(name="test flag")
        # self.now should be in the future relative to SETUP_TIME
        self.now = datetime(2026, 10, 8, tzinfo=UTC)

    def test_config_flag_with_no_experiments(self):
        self.assertEqual(
            snapshot(self.now),
            {"flags": {"test flag": {"enabled": False, "experiments": []}}},
        )

    def test_config_flag_with_ended_experiment(self):
        make_experiment(
            start_at=self.now - timedelta(days=4),
            end_at=self.now - timedelta(days=1),
            feature_flag=self.feature_flag,
        )

        self.assertEqual(
            len(snapshot(self.now)["flags"]["test flag"]["experiments"]), 0
        )

    def test_config_flag_with_unended_experiment(self):
        make_experiment(
            name="test experiment",
            start_at=self.now - timedelta(days=4),
            end_at=self.now + timedelta(days=3),
            feature_flag=self.feature_flag,
        )

        self.assertIn(
            "test-experiment",
            [
                e["slug"]
                for e in snapshot(self.now)["flags"]["test flag"]["experiments"]
            ],
        )

    def test_config_payload_structure(self):
        make_experiment(
            name="test experiment",
            start_at=self.now - timedelta(days=1),
            end_at=self.now + timedelta(days=1),
            feature_flag=self.feature_flag,
            hypothesis="The future",
            control=40,
            treatment=60,
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
                                "control": 40,
                                "treatment": 60,
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

        self.assertIn(
            "test-experiment",
            [
                e["slug"]
                for e in snapshot(self.now)["flags"]["test flag"]["experiments"]
            ],
        )

    def test_config_flag_experiment_ending_now_not_included(self):
        make_experiment(
            name="test experiment",
            start_at=self.now - timedelta(days=2),
            end_at=self.now,
            feature_flag=self.feature_flag,
        )

        self.assertNotIn(
            "test-experiment",
            [
                e["slug"]
                for e in snapshot(self.now)["flags"]["test flag"]["experiments"]
            ],
        )
