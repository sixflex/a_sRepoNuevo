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
]
