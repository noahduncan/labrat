import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import time_machine
from django.core.exceptions import NON_FIELD_ERRORS
from django.test import Client
from django.test.testcases import TestCase

from experimentation.models import Action, Exposure
from experimentation.tests.unit.models.test_experiment import make_experiment

SETUP_TIME = datetime(2026, 10, 1, tzinfo=UTC)
EXPERIMENT_START = SETUP_TIME + timedelta(minutes=5)
EXPERIMENT_END = SETUP_TIME + timedelta(days=1)
RECORD_EXPOSURE_URL = "/experimentation/api/v1/experiment/record-exposure"
RECORD_ACTION_URL = "/experimentation/api/v1/record-action"


class RecordActionViewTest(TestCase):
    def setUp(self):
        self.now = datetime.now(UTC)
        self.payload = {
            "name": "test_action",
            "subject": "11",
            "triggered_at": self.now.isoformat(),
        }

    def post(self, data, client=None):
        return (client or self.client).post(
            RECORD_ACTION_URL, data=data, content_type="application/json"
        )

    def test_record_action_positive(self):
        response = self.post(json.dumps(self.payload))

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        action = Action.objects.get()
        self.assertEqual(response.json(), {"action": action.pk})
        self.assertEqual(action.subject, "11")
        self.assertEqual(action.name, "test_action")
        self.assertEqual(action.triggered_at, self.now)

    def test_record_action_rejects_bad_body(self):
        bodies = {
            "malformed JSON": "{not json",
            "invalid UTF-8": b"\xff\xfe",
            "non-object JSON": "[1, 2]",
        }
        for case, body in bodies.items():
            with self.subTest(case):
                response = self.post(body)

                self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(
                    response.json(), {"errors": {NON_FIELD_ERRORS: ["Invalid JSON"]}}
                )

        self.assertFalse(Action.objects.exists())

    def test_record_action_rejects_missing_fields(self):
        for field in ["name", "subject", "triggered_at"]:
            with self.subTest(field):
                payload = {k: v for k, v in self.payload.items() if k != field}
                response = self.post(payload)
                self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(
                    response.json(),
                    {"errors": {field: ["This field is required."]}},
                )

    def test_record_action_rejects_get(self):
        response = self.client.get(RECORD_ACTION_URL)

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_record_action_is_csrf_exempt(self):
        # The default test client skips CSRF checks, so enforce them explicitly.
        response = self.post(
            json.dumps(self.payload), client=Client(enforce_csrf_checks=True)
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)


@time_machine.travel(SETUP_TIME, tick=False)
class RecordExposureViewTest(TestCase):
    def setUp(self):
        self.experiment = make_experiment(
            name="experiment slug",
            start_at=EXPERIMENT_START,
            end_at=EXPERIMENT_END,
            control=30,
            treatment=70,
        )
        # Subject "11" buckets into treatment for this experiment.
        self.payload = {
            "experiment": self.experiment.slug,
            "subject": "11",
            "variant": "treatment",
            "exposed_at": (EXPERIMENT_START + timedelta(hours=3)).isoformat(),
        }

    def post(self, data, client=None):
        return (client or self.client).post(
            RECORD_EXPOSURE_URL, data=data, content_type="application/json"
        )

    def test_record_exposure_positive(self):
        response = self.post(json.dumps(self.payload))

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
        exposure = Exposure.objects.get()
        self.assertEqual(response.json(), {"exposure": exposure.pk})
        self.assertEqual(exposure.experiment, self.experiment)
        self.assertEqual(exposure.subject, "11")
        self.assertEqual(exposure.variant, "treatment")

    def test_record_exposure_rejects_bad_body(self):
        bodies = {
            "malformed JSON": "{not json",
            "invalid UTF-8": b"\xff\xfe",
            "non-object JSON": "[1, 2]",
        }
        for case, body in bodies.items():
            with self.subTest(case):
                response = self.post(body)

                self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
                self.assertEqual(
                    response.json(), {"errors": {NON_FIELD_ERRORS: ["Invalid JSON"]}}
                )

        self.assertFalse(Exposure.objects.exists())

    def test_record_exposure_rejects_unknown_experiment(self):
        response = self.post(json.dumps({**self.payload, "experiment": "nope"}))

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("experiment", response.json()["errors"])
        self.assertFalse(Exposure.objects.exists())

    def test_record_exposure_rejects_model_validation_error(self):
        response = self.post(json.dumps({**self.payload, "variant": "control"}))

        self.assertEqual(response.status_code, HTTPStatus.BAD_REQUEST)
        self.assertIn("__all__", response.json()["errors"])
        self.assertFalse(Exposure.objects.exists())

    def test_record_exposure_rejects_get(self):
        response = self.client.get(RECORD_EXPOSURE_URL)

        self.assertEqual(response.status_code, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_record_exposure_is_csrf_exempt(self):
        # The default test client skips CSRF checks, so enforce them explicitly.
        response = self.post(
            json.dumps(self.payload), client=Client(enforce_csrf_checks=True)
        )

        self.assertEqual(response.status_code, HTTPStatus.CREATED)
