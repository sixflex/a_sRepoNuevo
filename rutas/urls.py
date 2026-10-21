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
        "actividad/<int:actividad_id>/sin-cierre/",
        views.indicar_sin_cierre,
        name="indicar_sin_cierre",
    ),
    path(
        "actividad/<int:actividad_id>/invitar-socios/",
        views.invitar_socios_cierre,
        name="invitar_socios_cierre",
    ),
    path(
        "invitacion/<int:invitacion_id>/reenviar/",
        views.reenviar_invitacion_cierre,
        name="reenviar_invitacion_cierre",
    ),
    path(
        "invitacion/<int:invitacion_id>/respuesta/",
        views.registrar_respuesta_cierre,
        name="registrar_respuesta_cierre",
    ),
    path(
        "cierre/<uuid:token>/<slug:respuesta>/",
        views.responder_invitacion_cierre,
        name="responder_invitacion_cierre",
    ),
    path(
        "formularios-qr/",
        views.formularios_qr,
        name="formularios_qr",
    ),
    path(
        'coordinacion/',
        views.seguimiento_rutas_coordinacion, 
        name='seguimiento_coordinacion'
    ),
    path(
        "coordinacion/<int:seccion_ruta_id>/",
        views.detalle_ruta_coordinacion,
        name="detalle_ruta_coordinacion",
    ),
    path(
        "coordinacion/<int:seccion_ruta_id>/expediente.zip",
        views.descargar_expediente,
        name="descargar_expediente",
    ),
]