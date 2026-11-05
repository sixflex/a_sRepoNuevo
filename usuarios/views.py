from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.http import require_POST

from . import entra, services
from .models import IdentidadInstitucional


# Modo "vincular otra cuenta": se guarda en la sesión (no se confía en un
# parámetro de la URL) y vence a los pocos minutos.
SESION_VINCULAR = "vincular_cuenta"
SESION_FUSION = "fusion_pendiente"
MINUTOS_VINCULAR = 10


def _modo_vincular(request):
    """True si esta sesión pidió vincular otra cuenta hace poco."""
    datos = request.session.get(SESION_VINCULAR)
    if not datos or not request.user.is_authenticated:
        return False
    if datos.get("usuario_id") != request.user.pk:
        return False
    return timezone.now().timestamp() - datos.get("desde", 0) < MINUTOS_VINCULAR * 60


def _destino_seguro(request, destino, por_defecto):
    if url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino
    return por_defecto


class LoginTemporalView(LoginView):
    template_name = "usuarios/login.html"
    # False: quien ya tiene sesión puede ver el login para cambiar de cuenta.
    redirect_authenticated_user = False

    def get(self, request, *args, **kwargs):
        # Volver al login cancela un "vincular otra cuenta" a medias.
        request.session.pop(SESION_VINCULAR, None)
        return super().get(request, *args, **kwargs)

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
            "dominios": entra.texto_dominios(),
            "vincular": _modo_vincular(request),
            "next": request.POST.get("next") or request.GET.get("next", ""),
            **extra,
        }

    def get(self, request):
        return render(request, self.template_name, self._contexto(request))

    def post(self, request):
        correo = request.POST.get("correo", "")

        if _modo_vincular(request):
            return self._vincular(request, correo)

        try:
            usuario, identidad = entra.autenticar_con_entra(correo)
        except entra.EntraError as error:
            contexto = self._contexto(request, error=str(error), correo=correo)
            return render(request, self.template_name, contexto)

        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        request.session[services.SESION_IDENTIDAD] = identidad.pk

        destino = _destino_seguro(request, request.POST.get("next", ""), settings.LOGIN_REDIRECT_URL)
        return redirect(destino)

    def _vincular(self, request, correo):
        """La otra cuenta se autenticó; la sesión sigue siendo la de siempre."""
        try:
            identidad_entra = entra.get_conector().identificar(correo)
            duenio, _ = services.duenio_de_cuenta(identidad_entra)
            if duenio is not None and duenio.pk != request.user.pk:
                services.comprobar_fusion(duenio, request.user)
        except entra.EntraError as error:
            contexto = self._contexto(request, error=str(error), correo=correo)
            return render(request, self.template_name, contexto)

        request.session.pop(SESION_VINCULAR, None)

        if duenio is not None and duenio.pk == request.user.pk:
            messages.info(request, f"{identidad_entra.correo} ya está vinculada a tu cuenta.")
            return redirect("usuarios:cuenta")

        if duenio is not None:
            request.session[SESION_FUSION] = {
                "usuario_id": duenio.pk,
                "correo": identidad_entra.correo,
                "oid": identidad_entra.oid,
                "tenant_id": identidad_entra.tenant_id,
            }
            return redirect("usuarios:cuenta_fusionar")

        services.vincular_identidad(
            request.user, identidad_entra, IdentidadInstitucional.CONFIRMADO_USUARIO, request=request,
        )
        messages.success(
            request,
            f"Listo: ahora también puedes entrar con {identidad_entra.correo}.",
        )
        return redirect("usuarios:cuenta")


@login_required
def cuenta(request):
    """Mi cuenta: las cuentas institucionales con las que la persona entra."""
    # Volver aquí cancela un "vincular otra cuenta" a medias.
    request.session.pop(SESION_VINCULAR, None)
    return render(request, "usuarios/cuenta.html", {
        "identidades": request.user.identidades.all(),
        "identidad_actual": services.identidad_actual(request),
        "dominios": entra.texto_dominios(),
        "entra_activo": entra.modo() == "simulado",
    })


@login_required
@require_POST
def cuenta_vincular(request):
    if entra.modo() != "simulado":
        messages.error(request, "La vinculación con Microsoft no está disponible.")
        return redirect("usuarios:cuenta")
    request.session[SESION_VINCULAR] = {
        "usuario_id": request.user.pk,
        "desde": timezone.now().timestamp(),
    }
    request.session.pop(SESION_FUSION, None)
    return redirect("usuarios:entra_login")


@login_required
def cuenta_fusionar(request):
    """Confirmación: la otra cuenta ya tenía datos en el portal."""
    pendiente = request.session.get(SESION_FUSION)
    if not pendiente:
        return redirect("usuarios:cuenta")

    from django.contrib.auth import get_user_model

    otro = get_user_model().objects.filter(pk=pendiente["usuario_id"]).first()
    if otro is None:
        request.session.pop(SESION_FUSION, None)
        return redirect("usuarios:cuenta")

    if request.method == "POST":
        request.session.pop(SESION_FUSION, None)
        if request.POST.get("accion") != "confirmar":
            messages.info(request, "No se vinculó la cuenta.")
            return redirect("usuarios:cuenta")
        try:
            services.fusionar_usuarios(
                otro, request.user, request=request,
                cuenta_confirmada=entra.IdentidadEntra(
                    oid=pendiente["oid"], correo=pendiente["correo"], nombre="", apellido="",
                    rol="", tenant_id=pendiente["tenant_id"],
                ),
            )
        except services.IdentidadError as error:
            messages.error(request, str(error))
            return redirect("usuarios:cuenta")
        messages.success(
            request,
            f"Listo: unimos {pendiente['correo']} a tu cuenta. Todo quedó en un solo lugar.",
        )
        return redirect("usuarios:cuenta")

    return render(request, "usuarios/cuenta_fusionar.html", {
        "correo": pendiente["correo"],
        "resumen": services.resumen_datos(otro),
    })


@login_required
@require_POST
def cuenta_principal(request, identidad_id):
    identidad = get_object_or_404(IdentidadInstitucional, pk=identidad_id, usuario=request.user)
    try:
        services.marcar_principal(request.user, identidad, request=request)
    except services.IdentidadError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"{identidad.correo} es ahora tu cuenta principal.")
    return redirect("usuarios:cuenta")


@login_required
@require_POST
def cuenta_desvincular(request, identidad_id):
    identidad = get_object_or_404(IdentidadInstitucional, pk=identidad_id, usuario=request.user)
    try:
        services.desvincular_identidad(
            request.user, identidad, services.identidad_actual(request), request=request,
        )
    except services.IdentidadError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Quitamos {identidad.correo} de tu cuenta.")
    return redirect("usuarios:cuenta")


@login_required
@require_POST
def ocultar_aviso_vincular(request):
    request.session[services.SESION_AVISO_OCULTO] = True
    return redirect(_destino_seguro(request, request.POST.get("next", ""), settings.LOGIN_REDIRECT_URL))
