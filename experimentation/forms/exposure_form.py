from django import forms

from experimentation.models import Experiment, Exposure


class ExposureForm(forms.Form):
    experiment = forms.ModelChoiceField(Experiment.objects.all(), to_field_name="slug")
    subject = forms.CharField(max_length=255)
    variant = forms.ChoiceField(choices=Exposure.Variant.choices)
    exposed_at = forms.DateTimeField()
