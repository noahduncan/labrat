from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/v1/config", views.config_snapshot),
    path("api/v1/experiment/record-exposure", views.record_exposure),
]
