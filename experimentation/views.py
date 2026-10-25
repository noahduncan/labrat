import json
from http import HTTPStatus

from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms.exposure_form import ExposureForm
from .services import config
from .services import exposure as exposure_service


def index(request):
    return HttpResponse("Hello, world. You're at the experimentation index")


@require_GET
def config_snapshot(request) -> JsonResponse:
    snapshot = config.snapshot()
    return JsonResponse(snapshot)


@require_POST
@csrf_exempt
def record_exposure(request) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse(
            data={"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST
        )

    if not isinstance(data, dict):
        return JsonResponse(
            data={"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST
        )

    form = ExposureForm(data)

    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=HTTPStatus.BAD_REQUEST)

    try:
        exposure = exposure_service.record(**form.cleaned_data)

        return JsonResponse(data={"exposure": exposure.pk}, status=HTTPStatus.CREATED)
    except ValidationError as e:
        return JsonResponse(
            data={"errors": e.message_dict}, status=HTTPStatus.BAD_REQUEST
        )
