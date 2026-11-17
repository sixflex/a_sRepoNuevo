from django.urls import path

from . import views

app_name = "comunicaciones"

urlpatterns = [
    path("correo-de-envio/", views.correo_envio, name="correo_envio"),
]
