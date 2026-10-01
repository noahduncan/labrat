from django.contrib import admin

from .models import FeatureFlag, Experiment

admin.site.register(FeatureFlag)
admin.site.register(Experiment)
