from django.urls import path

from . import views


app_name = "planificacion"


urlpatterns = [
    path(
        "formulario/<uuid:token>/", views.formulario_tabular_as, name="formulario_tabular_as",
    ),
]
