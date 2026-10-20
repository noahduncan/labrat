import warnings
from datetime import UTC, datetime

from labrat_client import bucketing
from labrat_client.exceptions import LabratWarning


class FlagResult:
    def __init__(
        self, enabled: bool, experiment_slug: str | None, variant: str | None
    ) -> None:
        self.enabled = enabled
        self.experiment_slug = experiment_slug
        self.variant = variant


def evaluate(
    flags: dict,
    flag_name: str,
    user_id: str,
    now: datetime | None = None,
    default: bool = False,
) -> FlagResult:
    now = now or datetime.now(UTC)
    flag = flags.get(flag_name)
    if flag is None:
        warnings.warn(f"Flag {flag_name} is not configured", LabratWarning)
        return FlagResult(default, None, None)

    experiments = flag.get("experiments")

    if not experiments:
        return FlagResult(flag["enabled"], None, None)

    for experiment in experiments:
        if experiment["start_at"] <= now < experiment["end_at"]:
            variant = bucketing.variant_for(
                experiment["slug"], experiment["control"], user_id
            )
            enabled = flag["enabled"] if variant == "control" else not flag["enabled"]
            return FlagResult(enabled, experiment["slug"], variant)

    return FlagResult(flag["enabled"], None, None)
