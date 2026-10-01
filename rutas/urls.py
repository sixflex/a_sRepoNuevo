from django.urls import path

from . import views

app_name = "rutas"

urlpatterns = [
    path(
        "docente/<int:seccion_ruta_id>/",
        views.detalle_ruta_docente,
        name="detalle_ruta_docente",
    ),
    path(
        "actividad/<int:actividad_id>/completar/",
        views.completar_actividad,
        name="completar_actividad",
    ),
]