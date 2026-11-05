from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views
from .views import EntraLoginSimuladoView, LoginTemporalView


app_name = "usuarios"


urlpatterns = [
    path(
        "login/",
        LoginTemporalView.as_view(),
        name="login",
    ),

    path(
        "login/microsoft/",
        EntraLoginSimuladoView.as_view(),
        name="entra_login",
    ),

    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),

    # Mi cuenta: cuentas institucionales vinculadas.
    path("cuenta/", views.cuenta, name="cuenta"),
    path("cuenta/vincular/", views.cuenta_vincular, name="cuenta_vincular"),
    path("cuenta/vincular/confirmar/", views.cuenta_fusionar, name="cuenta_fusionar"),
    path("cuenta/<int:identidad_id>/principal/", views.cuenta_principal, name="cuenta_principal"),
    path("cuenta/<int:identidad_id>/desvincular/", views.cuenta_desvincular, name="cuenta_desvincular"),
    path("cuenta/aviso/ocultar/", views.ocultar_aviso_vincular, name="ocultar_aviso_vincular"),
]
