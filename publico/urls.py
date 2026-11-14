from django.urls import path

from . import views

app_name = "publico"

urlpatterns = [
    path("", views.configurar_portal, name="configurar_portal"),
    path("noticias/", views.noticias, name="noticias"),
    path("noticias/<int:noticia_id>/estado/", views.cambiar_estado_noticia, name="cambiar_estado_noticia"),
    path("noticias/<int:noticia_id>/eliminar/", views.eliminar_noticia, name="eliminar_noticia"),
]
