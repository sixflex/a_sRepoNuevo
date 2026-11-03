from django.urls import path

from . import views

app_name = "reportes"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("participaciones/", views.participaciones, name="participaciones"),
    path("centros-sercotec/", views.centros_sercotec, name="centros_sercotec"),
]
