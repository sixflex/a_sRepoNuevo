from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('core.urls', 'core'), namespace='core')),
    path('academico/', include('academico.urls')),
    # Atajo corto a "Mi cuenta".
    path('cuenta/', RedirectView.as_view(pattern_name='usuarios:cuenta')),
    path('usuarios/', include(('usuarios.urls', 'usuarios'), namespace='usuarios')),
    path('socios/', include(('socios.urls', 'socios'), namespace='socios')),
    path('planificacion/', include('planificacion.urls')),
    path('archivos/', include('archivos.urls')),
    path('proyectos/', include(('proyectos.urls', 'proyectos'), namespace='proyectos')),
    path("rutas/", include("rutas.urls")),
    path("cartas/", include("cartas.urls")),
    path("formularios/", include(("encuestas.urls", "encuestas"), namespace="encuestas")),
    path("historicos/", include(("historicos.urls", "historicos"), namespace="historicos")),
    path("reportes/", include(("reportes.urls", "reportes"), namespace="reportes")),
    path("portal-publico/", include(("publico.urls", "publico"), namespace="publico")),
]
