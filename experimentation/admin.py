from django.contrib import admin

from .models import Experiment, FeatureFlag

admin.site.register(FeatureFlag)
admin.site.register(Experiment)
