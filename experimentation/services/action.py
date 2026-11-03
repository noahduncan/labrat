from datetime import datetime

from experimentation.models.action import Action


def record(*, name: str, subject: str, triggered_at: datetime) -> Action:
    return Action.objects.create(
        name=name,
        subject=subject,
        triggered_at=triggered_at,
    )
