from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('core.urls', 'core'), namespace='core')),
    path('academico/', include('academico.urls')),
    path('usuarios/', include(('usuarios.urls', 'usuarios'), namespace='usuarios')),
    path('socios/', include(('socios.urls', 'socios'), namespace='socios')),
    path('planificacion/', include('planificacion.urls')),
<<<<<<< HEAD
    path("socios/", include("socios.urls")),
    path('archivos/', include('archivos.urls')),
]
=======
    path('proyectos/', include(('proyectos.urls', 'proyectos'), namespace='proyectos')),
]
>>>>>>> 232e647dd2c417811398679c1dd1f21dafe258ed
