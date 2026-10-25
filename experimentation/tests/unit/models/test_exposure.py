from datetime import UTC, datetime, timedelta

import time_machine
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.test.testcases import TestCase

from experimentation.models import Exposure
from experimentation.tests.unit.models.test_experiment import make_experiment

SETUP_TIME = datetime(2026, 10, 1, tzinfo=UTC)
EXPERIMENT_START = SETUP_TIME + timedelta(minutes=5)
EXPERIMENT_END = SETUP_TIME + timedelta(days=1)


@time_machine.travel(SETUP_TIME)
class ExposureTest(TestCase):
    def setUp(self):
        self.experiment = make_experiment(
            name="experiment slug",
            start_at=EXPERIMENT_START,
            end_at=EXPERIMENT_END,
            control=30,
            treatment=70,
        )

    def create_exposure(self, **overrides) -> Exposure:
        # Defaults describe a valid exposure: subject "11" buckets into treatment.
        fields = {
            "experiment": self.experiment,
            "subject": "11",
            "variant": "treatment",
            "exposed_at": EXPERIMENT_START + timedelta(hours=3),
            **overrides,
        }
        return Exposure.objects.create(**fields)

    def test_create_exposure_positive(self):
        # Subjects chosen so swapped arg or wrong split changes the variant.
        # This confirms that variant_for() in clean is wired correctly.
        for subject, variant in [("11", "treatment"), ("16", "control")]:
            with self.subTest(subject=subject, variant=variant):
                exposure = self.create_exposure(subject=subject, variant=variant)

                exposure.refresh_from_db()
                self.assertEqual(exposure.experiment, self.experiment)
                self.assertEqual(exposure.subject, subject)
                self.assertEqual(exposure.variant, variant)

    def test_create_exposure_raises_outside_experiment_window(self):
        for exposure_time in (EXPERIMENT_START - timedelta(days=3), EXPERIMENT_END):
            with self.subTest(exposure_time=exposure_time):
                with self.assertRaises(ValidationError) as cm:
                    self.create_exposure(exposed_at=exposure_time)

                self.assertEqual(
                    cm.exception.error_dict[NON_FIELD_ERRORS][0].code,
                    "outside_experiment_window",
                )

    def test_create_exposure_raises_with_wrong_variant(self):
        with self.assertRaises(ValidationError) as cm:
            self.create_exposure(variant="control")

        self.assertEqual(
            cm.exception.error_dict[NON_FIELD_ERRORS][0].code, "incorrect_variant"
        )

    def test_create_exposure_raises_validationerror_when_no_experiment(self):
        with self.assertRaises(ValidationError):
            self.create_exposure(experiment=None)
