
from django.urls import path

from . import views

urlpatterns = [
    path("", views.cargas, name="cargas"),
    path("consulta/",views.consulta_historicos,name="consulta_historicos",),
    path("consulta/exportar/",views.exportar_historicos,name="exportar_historicos",),
    path("<int:carga_id>/", views.detalle, name="detalle"),
    path("<int:carga_id>/confirmar/", views.confirmar, name="confirmar"),
    path("<int:carga_id>/cancelar/", views.cancelar, name="cancelar"),
]
