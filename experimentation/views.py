from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .services import config


def index(request):
    return HttpResponse("Hello, world. You're at the experimentation index")


@require_GET
def config_snapshot(request) -> JsonResponse:
    snapshot = config.snapshot()
    return JsonResponse(snapshot)

