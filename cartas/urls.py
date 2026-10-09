from django.urls import path

from . import views


app_name = "cartas"


urlpatterns = [
    path(
        "docente/seccion/<int:seccion_id>/solicitar/",
        views.solicitar_carta_docente,
        name="solicitar_carta_docente",
    ),
    path(
        "coordinacion/",
        views.listar_solicitudes_coordinacion,
        name="listar_solicitudes_coordinacion",
    ),
    path(
        "coordinacion/<int:solicitud_id>/",
        views.detalle_solicitud_coordinacion,
        name="detalle_solicitud_coordinacion",
    ),
    path(
        "coordinacion/<int:solicitud_id>/aprobar/",
        views.aprobar_solicitud,
        name="aprobar_solicitud",
    ),
    path(
        "coordinacion/<int:solicitud_id>/observar/",
        views.observar_solicitud,
        name="observar_solicitud",
    ),
    path(
    "docente/solicitud/<int:solicitud_id>/editar/",
    views.editar_solicitud_docente,
    name="editar_solicitud_docente",
    ),
    path(
    "coordinacion/<int:solicitud_id>/generar-pdf/",
    views.generar_carta_pdf,
    name="generar_carta_pdf",
    ),
]