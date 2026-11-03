from typing import ClassVar

from django.db import models


class Action(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_comment="The moment the record was created.",
    )
    triggered_at = models.DateTimeField(
        db_comment="The moment the action was triggered."
    )
    name = models.CharField(max_length=255, db_comment="The name of the action.")
    subject = models.CharField(
        max_length=255,
        db_comment="The subject performing the action.",
    )

    class Meta:
        indexes: ClassVar[list[models.Index]] = [
            # Likely used during analytics when joining exposures to actions
            models.Index(fields=["name", "subject", "triggered_at"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.subject} - {self.triggered_at}"
