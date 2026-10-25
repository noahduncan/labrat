from collections import defaultdict

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models
from labrat_client import bucketing

from .experiment import Experiment


class Exposure(models.Model):
    class Variant(models.TextChoices):
        CONTROL = "control", "Control"
        TREATMENT = "treatment", "Treatment"

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        db_comment="The moment that this record was created.",
    )
    exposed_at = models.DateTimeField(
        null=False,
        blank=False,
        db_index=True,
        db_comment="The moment the client exposed this feature to the end user.",
    )
    experiment = models.ForeignKey(
        Experiment, on_delete=models.PROTECT, null=False, db_index=True
    )
    subject = models.CharField(max_length=255, null=False, blank=False, db_index=True)
    variant = models.CharField(
        choices=Variant.choices, max_length=9, null=False, blank=False, db_index=True
    )
    # Add a fields for late_exposure, incorrect_variant?

    def __str__(self):
        return f"{self.experiment.name} - {self.get_variant_display()} - {self.subject}"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = defaultdict(list)

        if (
            self.experiment_id
            and self.exposed_at
            and (
                self.experiment.start_at > self.exposed_at
                or self.exposed_at >= self.experiment.end_at
            )
        ):
            errors[NON_FIELD_ERRORS].append(
                ValidationError(
                    "Experiment not active when exposed.", "outside_experiment_window"
                )
            )

        if self.experiment_id and self.variant != bucketing.variant_for(
            self.experiment.slug, self.experiment.control, self.subject
        ):
            errors[NON_FIELD_ERRORS].append(
                ValidationError("Incorrect variant provided.", "incorrect_variant")
            )

        """
        Validations to consider:
        * exposed_at must be < now
        """

        if errors:
            raise ValidationError(errors)
