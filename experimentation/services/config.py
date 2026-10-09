from datetime import datetime

from django.db.models.query import Prefetch
from django.utils import timezone

from experimentation.models import Experiment, FeatureFlag


def snapshot(now : datetime | None = None):
    now = now or timezone.now()
    current_experiments = Experiment.objects.filter(end_at__gt=now).order_by("start_at")

    flags = FeatureFlag.objects.prefetch_related(
        Prefetch(
            "experiment_set",
            queryset=current_experiments,
            to_attr="current_experiments",
        ),
    )

    return {
        "flags": {
            f.name: {
                "enabled": f.enabled,
                "experiments": [
                    {
                        "name": e.name,
                        "slug": e.slug,
                        "split_a": e.split_a,
                        "split_b": e.split_b,
                        "start_at": e.start_at,
                        "end_at": e.end_at,
                    }
                    for e in f.current_experiments
                ],
            }
            for f in flags
        }
    }
