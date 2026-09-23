from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('coordinacion/validar-planificacion/', views.validar_planificacion_view, name='validar_planificacion'),
]