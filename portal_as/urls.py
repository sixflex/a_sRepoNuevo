from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('core.urls', 'core'), namespace='core')),
    path('usuarios/', include(('usuarios.urls', 'usuarios'), namespace='usuarios')),
    path('planificacion/', include('planificacion.urls')),
    path('proyectos/', include(('proyectos.urls', 'proyectos'), namespace='proyectos')),
]
