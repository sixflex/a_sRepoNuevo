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
        "docente/<int:seccion_ruta_id>/completar/",
        views.completar_ruta,
        name="completar_ruta",
    ),
    path(
        "actividad/<int:actividad_id>/completar/",
        views.completar_actividad,
        name="completar_actividad",
    ),
    path(
        "actividad/<int:actividad_id>/evidencia/",
        views.subir_evidencia,
        name="subir_evidencia",
    ),
    path(
        "evidencia/<int:evidencia_id>/eliminar/",
        views.eliminar_evidencia,
        name="eliminar_evidencia",
    ),
    path(
        "coordinacion/",
        views.seguimiento_rutas_coordinacion,
        name="seguimiento_rutas_coordinacion",
    ),
    path(
        "coordinacion/<int:seccion_ruta_id>/",
        views.detalle_ruta_coordinacion,
        name="detalle_ruta_coordinacion",
    ),
]