from django.urls import path
from . import views

app_name = "socios"

urlpatterns = [
    path("catalogo/", views.catalogo_socios_docente, name="catalogo_docente"),
    path("coordinacion/", views.lista_socios_coordinador, name="lista_coordinador"),
    path("coordinacion/<int:socio_id>/cambiar-estado/", views.cambiar_estado_socio, name="cambiar_estado"),
    path("coordinacion/<int:socio_id>/historial/", views.detalle_historial_socio, name="detalle_historial"),
    path("postulaciones/", views.lista_postulaciones, name="lista_postulaciones"),
    path("postulaciones/<int:postulacion_id>/revisar/", views.revisar_postulacion, name="revisar_postulacion"),
    path("ruta/actividad/<int:actividad_id>/asociar-socio/", views.asociar_socio_equipo, name="asociar_socio_equipo"),

    path("postular/", views.postular_publico, name="postular_publico"),
    path("postular/<int:convocatoria_id>/", views.postular_publico, name="postular_convocatoria"),
    path("postular/confirmacion/<int:postulacion_id>/", views.postulacion_exitosa, name="postulacion_exitosa"),
]