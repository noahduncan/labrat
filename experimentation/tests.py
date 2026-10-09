from datetime import timedelta
from itertools import count

from django.test.testcases import TestCase
from django.utils import timezone

from .models import Experiment, FeatureFlag

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
