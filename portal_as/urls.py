

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('academico/', include('academico.urls')),
    path('usuarios/', include('usuarios.urls')),
    path('proyectos/', include('proyectos.urls')),
    path('planificacion/', include('planificacion.urls')),
    path("socios/", include("socios.urls")),
]