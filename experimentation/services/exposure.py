from datetime import datetime

from experimentation.models import Experiment
from experimentation.models.exposure import Exposure


def record(
    *, experiment: Experiment, subject: str, variant: str, exposed_at: datetime
) -> Exposure:
    e = Exposure.objects.create(
        experiment=experiment,
        variant=variant,
        exposed_at=exposed_at,
        subject=subject,
    )
    return e
