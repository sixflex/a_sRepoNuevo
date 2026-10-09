from django.urls import path

from . import views


app_name = "core"


urlpatterns = [
    path("", views.inicio, name="inicio"),

    path("coordinacion/", views.panel_coordinacion, name="coordinacion"),

    path("docente/", views.panel_docente, name="docente"),

    path("docente/inicio/", views.inicio_docente, name="inicio_docente"),
    
    path("secciones/<int:seccion_id>/", views.detalle_seccion, name="detalle_seccion"),

    path("coordinacion/planificacion/", views.planificacion_coordinacion, name="planificacion_coordinacion"),

    path("coordinacion/planificacion/<int:planificacion_id>/", views.detalle_planificacion_coordinacion, name="detalle_planificacion_coordinacion"),

    
    path("coordinacion/validar-planificacion/", views.validar_planificacion_view, name="validar_planificacion"),
]