from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    # Flujo demostrable Sprint 1
    path('coordinador-contexto/', views.coordinador_contexto, name='coordinador_contexto'),
    path('formulario-prueba/', views.formulario_prueba, name='formulario_prueba'),

    # SP2-T05: Generación y Gestión de Enlaces de Planificación
    path('enlaces-planificacion/', views.gestionar_enlaces_planificacion, name='gestionar_enlaces'),
    path('planificacion/<uuid:token>/', views.formulario_planificacion_docente, name='formulario_planificacion'),
]