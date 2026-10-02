from django.db import models


class FeatureFlag(models.Model):
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=False,null=False)

    def __str__(self):
        return self.name

class Experiment(models.Model):
    feature_flag = models.ForeignKey(FeatureFlag, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    prediction = models.TextField()
    split1 = models.IntegerField(default=50)
    split2 = models.IntegerField(default=50)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    def __str__(self):
        return self.name
