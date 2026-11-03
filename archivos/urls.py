from django.urls import path

from . import views

app_name = "archivos"

urlpatterns = [
    path(
        "<int:pk>/descargar/",
        views.descargar_archivo,
        name="descargar",
    ),
    # Repositorio (RF-PUB-02): administración del Coordinador.
    path("repositorio/", views.repositorio, name="repositorio"),
    path("repositorio/nuevo/", views.crear_recurso, name="crear_recurso"),
    path("repositorio/<int:pk>/editar/", views.editar_recurso, name="editar_recurso"),
    path("repositorio/<int:pk>/estado/", views.cambiar_estado_recurso, name="cambiar_estado_recurso"),
    path("repositorio/<int:pk>/eliminar/", views.eliminar_recurso, name="eliminar_recurso"),
    path("repositorio/<int:pk>/descargar/", views.descargar_recurso, name="descargar_recurso"),
    # Portal público, sin sesión.
    path("publico/", views.repositorio_publico, name="repositorio_publico"),
    path("publico/<int:pk>/descargar/", views.descargar_recurso_publico, name="descargar_recurso_publico"),
]
