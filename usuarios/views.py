from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from . import entra


class LoginTemporalView(LoginView):
    template_name = "usuarios/login.html"
    # False: quien ya tiene sesión puede ver el login para cambiar de cuenta.
    redirect_authenticated_user = False

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["entra_activo"] = entra.modo() == "simulado"
        return contexto


class EntraLoginSimuladoView(View):
    """Pantalla simulada de Microsoft (Entra ID) y su validación."""

    template_name = "usuarios/entra_simulado.html"

    def dispatch(self, request, *args, **kwargs):
        if entra.modo() != "simulado":
            raise Http404("El acceso simulado con Microsoft está desactivado.")
        return super().dispatch(request, *args, **kwargs)

    def _contexto(self, request, **extra):
        return {
            "cuentas": entra.CUENTAS_PRUEBA,
            "dominio": entra.dominio_permitido(),
            "next": request.POST.get("next") or request.GET.get("next", ""),
            **extra,
        }

    def get(self, request):
        return render(request, self.template_name, self._contexto(request))

    def post(self, request):
        correo = request.POST.get("correo", "")

        try:
            usuario = entra.autenticar_con_entra(correo)
        except entra.EntraError as error:
            contexto = self._contexto(request, error=str(error), correo=correo)
            return render(request, self.template_name, contexto)

        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")

        destino = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            destino,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            destino = settings.LOGIN_REDIRECT_URL
        return redirect(destino)
