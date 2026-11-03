import json
from http import HTTPStatus

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms.action_form import ActionForm
from .forms.exposure_form import ExposureForm
from .services import action as action_service
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
def record_action(request) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse(
            {"errors": {NON_FIELD_ERRORS: ["Invalid JSON"]}},
            status=HTTPStatus.BAD_REQUEST,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"errors": {NON_FIELD_ERRORS: ["Invalid JSON"]}},
            status=HTTPStatus.BAD_REQUEST,
        )

    form = ActionForm(data)

    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=HTTPStatus.BAD_REQUEST)

    action_service.record(**form.cleaned_data)

    return JsonResponse({}, status=HTTPStatus.OK)


@require_POST
@csrf_exempt
def record_exposure(request) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse(
            {"errors": {NON_FIELD_ERRORS: ["Invalid JSON"]}},
            status=HTTPStatus.BAD_REQUEST,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"errors": {NON_FIELD_ERRORS: ["Invalid JSON"]}},
            status=HTTPStatus.BAD_REQUEST,
        )

    form = ExposureForm(data)

    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=HTTPStatus.BAD_REQUEST)

    try:
        exposure_service.record(**form.cleaned_data)
    except ValidationError as e:
        return JsonResponse(
            data={"errors": e.message_dict}, status=HTTPStatus.BAD_REQUEST
        )

    return JsonResponse({}, status=HTTPStatus.OK)
