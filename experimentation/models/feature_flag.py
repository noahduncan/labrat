from django.db import models


class FeatureFlag(models.Model):
    name = models.CharField(max_length=255, unique=True)
    enabled = models.BooleanField(default=False, null=False)

    def __str__(self):
        return self.name
