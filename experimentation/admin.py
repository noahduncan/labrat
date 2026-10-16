from django.contrib import admin
from django.utils import timezone

from .models import Experiment, FeatureFlag

admin.site.register(FeatureFlag)


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.start_at <= timezone.now():
            return (
                "feature_flag",
                "hypothesis",
                "control",
                "treatment",
                "start_at",
                "end_at",
            )

        return ()
