from typing import ClassVar

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify

from .feature_flag import FeatureFlag


class Experiment(models.Model):
    feature_flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, editable=False)
    hypothesis = models.TextField()
    control = models.IntegerField(
        default=50,
        db_comment="% of users who see the control",
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )
    treatment = models.IntegerField(
        default=50,
        db_comment="% of users who see the treatment",
        validators=[MinValueValidator(1), MaxValueValidator(99)],
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    class Meta:
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(treatment=100 - models.F("control")),
                name="experiment_split_sums_to_100",
                violation_error_message="'control' and 'treatment' must sum to 100",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)

        # TODO Consider moving to service layer to prevent duplicate calls in some cases.
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        field_errors = {}
        non_field_errors = []

        if self.start_at and self.end_at and self.end_at <= self.start_at:
            non_field_errors.append(
                ValidationError("'end_at' must be after 'start_at'")
            )

        # Check for any other experiments with an overlapping start/end range.
        # We can't run multiple experiments on the same flag at the same time.
        if (
            self.feature_flag_id
            and self.start_at
            and self.end_at
            and Experiment.objects.filter(
                feature_flag_id=self.feature_flag_id,
                start_at__lt=self.end_at,
                end_at__gt=self.start_at,
            )
            .exclude(id=self.id)
            .exists()
        ):
            non_field_errors.append(
                ValidationError("This experiment overlaps with another experiment.")
            )

        if non_field_errors:
            field_errors[NON_FIELD_ERRORS] = non_field_errors

        if field_errors:
            raise ValidationError(field_errors)
