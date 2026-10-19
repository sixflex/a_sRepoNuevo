from django.urls import path

from . import views

urlpatterns = [
    path("", views.cargas, name="cargas"),
    path("<int:carga_id>/", views.detalle, name="detalle"),
    path("<int:carga_id>/confirmar/", views.confirmar, name="confirmar"),
    path("<int:carga_id>/cancelar/", views.cancelar, name="cancelar"),
]
