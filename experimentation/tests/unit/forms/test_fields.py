from datetime import UTC, date, datetime, timedelta, timezone

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from experimentation.forms.fields import AwareDateTimeField


class AwareDateTimeFieldTest(SimpleTestCase):
    def setUp(self):
        self.field = AwareDateTimeField()

    def assertErrorCode(self, value, code):
        with self.assertRaises(ValidationError) as cm:
            self.field.clean(value)

        self.assertEqual(cm.exception.code, code)

    def test_accepts_aware_values(self):
        noon_utc = datetime(2026, 10, 25, 12, tzinfo=UTC)
        mountain = timezone(timedelta(hours=-6))
        values = {
            "2026-10-25T12:00:00Z": noon_utc,
            "2026-10-25T12:00:00+00:00": noon_utc,
            " 2026-10-25T12:00:00Z ": noon_utc,
            "2026-10-25T06:00:00-06:00": datetime(2026, 10, 25, 6, tzinfo=mountain),
            noon_utc: noon_utc,
        }
        for value, expected in values.items():
            with self.subTest(value=value):
                result = self.field.clean(value)

                self.assertEqual(result, expected)
                # Equal instants can still differ in offset, so check it too.
                self.assertEqual(result.utcoffset(), expected.utcoffset())

    def test_rejects_values_without_offset_as_naive(self):
        values = [
            "2026-10-25T12:00:00",
            "2026-10-25",
            datetime(2026, 10, 25, 12),  # noqa: DTZ001 - naive on purpose
            date(2026, 10, 25),
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertErrorCode(value, "naive_datetime")

    def test_rejects_unparseable_values_as_invalid(self):
        values = [
            "garbage",
            # Django's DATETIME_INPUT_FORMATS never carry an offset.
            "10/25/2026 14:30",
            # Matches the ISO pattern but isn't a real date.
            "2026-13-45T12:00:00Z",
            12345,
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertErrorCode(value, "invalid")

    def test_rejects_empty_values_as_required(self):
        for value in ("", None):
            with self.subTest(value=value):
                self.assertErrorCode(value, "required")

    def test_returns_none_for_empty_value_when_optional(self):
        self.assertIsNone(AwareDateTimeField(required=False).clean(""))
