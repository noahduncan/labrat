from datetime import timedelta

import pytest
import time_machine
from django.utils import timezone
from labrat_client import LabratClient

from experimentation.models import Experiment, Exposure, FeatureFlag


@pytest.mark.django_db(transaction=True)
def test_client_records_exposure_end_to_end(live_server):
    now = timezone.now()
    feature_flag = FeatureFlag.objects.create(name="test flag")
    with time_machine.travel(now - timedelta(days=2)):
        experiment = Experiment.objects.create(
            name="test experiment",
            hypothesis="Improve conversions by 1%",
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1),
            feature_flag=feature_flag,
        )

    client = LabratClient(base_url=live_server.url + "/experimentation/api/v1")
    try:
        client.is_flag_on("test flag", "user-1")
    finally:
        client.close()

    assert Exposure.objects.filter(experiment=experiment, subject="user-1").exists()
