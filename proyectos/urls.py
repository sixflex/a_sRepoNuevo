from django.urls import path

from . import views


app_name = "proyectos"


urlpatterns = [
    # Flujo demostrable Sprint 1. Mantener solo mientras siga siendo útil.
    path( "coordinador-contexto/", views.coordinador_contexto, name="coordinador_contexto",
    ),

    # SP2-T05: generación y gestión de enlaces de planificación.
    path( "enlaces-planificacion/", views.gestionar_enlaces_planificacion, name="gestionar_enlaces",
    ),
    path(
    "secciones/<int:seccion_id>/registro-equipos/",
    views.gestionar_registro_equipos,
    name="gestionar_registro_equipos",
),
    path(
    "registro-equipos/<uuid:token>/",
    views.acceso_registro_equipos,
    name="acceso_registro_equipos",
),
    path(
    "secciones/<int:seccion_id>/equipos/",
    views.gestionar_equipos_seccion,
    name="gestionar_equipos_seccion",
),
    path(
    "equipos/<int:equipo_id>/gestionar/",
    views.gestionar_equipo,
    name="gestionar_equipo",
),
]
