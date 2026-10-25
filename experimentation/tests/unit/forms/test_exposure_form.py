from django.test import SimpleTestCase

from experimentation.forms.exposure_form import ExposureForm


class ExposureFormTest(SimpleTestCase):
    def test_rejects_naive_exposed_at(self):
        # Only checks that the form uses AwareDateTimeField; the field's own
        # behavior is covered in test_fields.py.
        form = ExposureForm({"exposed_at": "2026-10-25T12:00:00"})

        self.assertFalse(form.is_valid())
        self.assertIn("exposed_at", form.errors)
        self.assertEqual(form.errors.as_data()["exposed_at"][0].code, "naive_datetime")
