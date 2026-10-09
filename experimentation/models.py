from django.db import models
from django.utils.text import slugify


class FeatureFlag(models.Model):
    name = models.CharField(max_length=255, unique=True)
    enabled = models.BooleanField(default=False, null=False)

    def __str__(self):
        return self.name

class Experiment(models.Model):
    feature_flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, editable=False)
    prediction = models.TextField()
    split_a = models.IntegerField(default=50, db_comment="% of users who see the control")
    split_b = models.IntegerField(default=50, db_comment="% of users who see the treatment")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)
