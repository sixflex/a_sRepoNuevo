from django.urls import path

from . import views

app_name = "archivos"

urlpatterns = [
    path(
        "<int:pk>/descargar/",
        views.descargar_archivo,
        name="descargar",
    ),
]
