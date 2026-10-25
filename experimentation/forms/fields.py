from datetime import date, datetime

from django import forms
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _


class AwareDateTimeField(forms.DateTimeField):
    default_error_messages = {  # noqa: RUF012
        "naive_datetime": _("Timestamp must include a timezone offset.")
    }

    def to_python(self, value: str | datetime | date | None) -> datetime | None:
        """
        Validate that the value can represent a datetime with a timezone.
        """
        if value in self.empty_values:
            return None

        if isinstance(value, datetime):
            result = value
        elif isinstance(value, date):
            raise forms.ValidationError(
                self.error_messages["naive_datetime"], code="naive_datetime"
            )
        elif isinstance(value, str):
            try:
                result = parse_datetime(value.strip())
            except ValueError as e:
                raise forms.ValidationError(
                    self.error_messages["invalid"], code="invalid"
                ) from e
        else:
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")

        if result is None:
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")

        if result.utcoffset() is None:
            raise forms.ValidationError(
                self.error_messages["naive_datetime"], code="naive_datetime"
            )

        return result
