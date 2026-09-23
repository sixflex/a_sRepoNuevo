from django.contrib import admin
from django.urls import path, include
from core.views import validar_planificacion_view

urlpatterns = [
    path('', include('core.urls')),
    path('admin/', admin.site.urls),
    path('coordinacion/validar-planificacion/', validar_planificacion_view, name='validar_planificacion'),
]
