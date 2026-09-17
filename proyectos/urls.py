from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    path('coordinador-contexto/', views.coordinador_contexto, name='coordinador_contexto'),
    path('formulario-prueba/', views.formulario_prueba, name='formulario_prueba'),
]