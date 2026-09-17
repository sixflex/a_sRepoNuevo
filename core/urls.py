from django.urls import path

from . import views


app_name = "core"


urlpatterns = [
    path("", views.inicio, name="inicio",),

    path("coordinacion/", views.panel_coordinacion,name="coordinacion",),

    path("docente/", views.panel_docente, name="docente",),
    
    path("secciones/<int:seccion_id>/", views.detalle_seccion, name="detalle_seccion",),
]