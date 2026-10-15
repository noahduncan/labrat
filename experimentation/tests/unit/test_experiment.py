from datetime import timedelta
from itertools import count

import time_machine
from django.core.exceptions import ValidationError
from django.test.testcases import TestCase
from django.utils import timezone

from experimentation.models import Experiment, FeatureFlag

_counter = count(1)


def make_experiment(**overrides):
    now = timezone.now() + timedelta(minutes=5)
    fields = {
        "name": "test experiment" + str(next(_counter)),
        "hypothesis": "The future",
        "start_at": now,
        "end_at": now + timedelta(days=1),
        "control": 40,
        "treatment": 60,
        **overrides,
    }
    if "feature_flag" not in fields:
        fields["feature_flag"] = FeatureFlag.objects.create(
            name="test feature flag" + str(next(_counter))
        )

    return Experiment.objects.create(**fields)


class ExperimentTest(TestCase):
    def setUp(self):
        self.feature_flag = FeatureFlag.objects.create(name="test feature flag")
        self.now = timezone.now() + timedelta(minutes=5)

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
        with self.assertRaises(ValidationError) as cm:
            make_experiment(
                start_at=self.now + timedelta(days=1),
                end_at=self.now + timedelta(days=2),
                feature_flag=self.feature_flag,
            )
        self.assertEqual(
            cm.exception.error_dict["__all__"][0].code, "experiment_overlap"
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
        with self.assertRaises(ValidationError) as cm:
            make_experiment(
                start_at=self.now + timedelta(days=1),
                end_at=self.now + timedelta(days=2),
                feature_flag=self.feature_flag,
            )
        self.assertEqual(
            cm.exception.error_dict["__all__"][0].code, "experiment_overlap"
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
                control=40,
                treatment=40,
            )

        self.assertTrue("must sum to 100" in cm.exception.messages[0])

    def test_experiment_error_if_control_not_in_range(self):
        for value, code in [(-10, "min_value"), (0, "min_value"), (100, "max_value")]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as cm:
                    make_experiment(control=value, treatment=50)
                self.assertEqual(cm.exception.error_dict["control"][0].code, code)

    def test_experiment_error_if_treatment_not_in_range(self):
        for value, code in [(-10, "min_value"), (0, "min_value"), (100, "max_value")]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as cm:
                    make_experiment(control=50, treatment=value)
                self.assertEqual(cm.exception.error_dict["treatment"][0].code, code)

    def test_experiment_start_at_must_be_in_future(self):
        with self.assertRaises(ValidationError) as cm:
            make_experiment(start_at=self.now - timedelta(days=1), end_at=self.now)
        self.assertEqual(
            cm.exception.error_dict["start_at"][0].code, "datetime_in_past"
        )

        with time_machine.travel(self.now, tick=False):
            with self.assertRaises(ValidationError) as cm:
                make_experiment(start_at=self.now, end_at=self.now + timedelta(days=1))
            self.assertEqual(
                cm.exception.error_dict["start_at"][0].code, "datetime_in_past"
            )

    def test_experiment_start_at_must_be_before_end_at(self):
        with self.assertRaises(ValidationError) as cm:
            make_experiment(start_at=self.now, end_at=self.now - timedelta(days=1))
        self.assertEqual(cm.exception.error_dict["__all__"][0].code, "end_before_start")

    def test_experiment_cannot_edit_field_after_start_at(self):
        for field, value in [
            ("feature_flag", self.feature_flag),
            ("start_at", self.now + timedelta(days=1)),
            ("end_at", self.now + timedelta(days=4)),
            ("hypothesis", "I want to change"),
            ("control", 50),
            ("treatment", 50),
        ]:
            with self.subTest(field=field):
                e = make_experiment()
                setattr(e, field, value)
                with time_machine.travel(e.start_at + timedelta(hours=1), tick=False):
                    with self.assertRaises(ValidationError) as cm:
                        e.save()

                    self.assertEqual(
                        cm.exception.error_dict[field][0].code,
                        "locked_after_start",
                    )

    def test_experiment_can_edit_name_after_start_at(self):
        e = make_experiment()
        e.name = "This is my new name"
        with time_machine.travel(e.start_at + timedelta(hours=1), tick=False):
            e.save()
            e.refresh_from_db()
            self.assertEqual(e.name, "This is my new name")

    def test_experiment_can_edit_name_after_end_at(self):
        e = make_experiment()
        e.name = "This is my new name"
        with time_machine.travel(e.end_at + timedelta(hours=1), tick=False):
            e.save()
            e.refresh_from_db()
            self.assertEqual(e.name, "This is my new name")

    def test_experiment_fields_are_editable_before_start_at(self):
        for field, value in [
            ("feature_flag", self.feature_flag),
            ("start_at", self.now + timedelta(hours=1)),
            ("end_at", self.now + timedelta(days=4)),
            ("hypothesis", "I want to change"),
        ]:
            with self.subTest(field=field):
                e = make_experiment()
                setattr(e, field, value)
                e.save()

                e.refresh_from_db()
                self.assertEqual(getattr(e, field), value)

        e = make_experiment()
        e.control = 50
        e.treatment = 50
        e.save()

        e.refresh_from_db()
        self.assertEqual(e.control, 50)
        self.assertEqual(e.treatment, 50)

    def test_experiment_from_db_cannot_edit_fields_after_start_at(self):
        experiment_id = make_experiment().id
        e = Experiment.objects.get(id=experiment_id)

        with time_machine.travel(e.start_at + timedelta(hours=1), tick=False):
            with self.assertRaises(ValidationError) as cm:
                e.hypothesis = "I want to change"
                e.save()
            self.assertEqual(
                cm.exception.error_dict["hypothesis"][0].code, "locked_after_start"
            )
