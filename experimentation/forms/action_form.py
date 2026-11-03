from typing import ClassVar

from django import forms

from experimentation.forms.fields import AwareDateTimeField
from experimentation.models import Action


class ActionForm(forms.ModelForm):
    class Meta:
        model = Action
        fields = ("name", "subject", "triggered_at")
        field_classes: ClassVar[dict[str, type[forms.Field]]] = {
            "triggered_at": AwareDateTimeField
        }
