from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage, get_connection
from django.shortcuts import redirect, render
from django.utils import timezone

from auditoria.services import registrar_auditoria
from usuarios.decorators import coordinador_required

from . import configuracion as config
from .forms import ConfiguracionCorreoForm, CorreoPruebaForm
from .models import ConfiguracionCorreo, EnvioCorreo


def _auditable(configuracion):
    """Lo que queda en auditoría: nunca la clave, solo si existe."""
    if configuracion is None or configuracion.pk is None:
        return None
    return {
        "remitente_nombre": configuracion.remitente_nombre,
        "remitente_correo": configuracion.remitente_correo,
        "responder_a": configuracion.responder_a,
        "servidor_smtp": configuracion.servidor_smtp,
        "puerto": configuracion.puerto,
        "activo": configuracion.activo,
        "tiene_clave": bool(configuracion.clave_cifrada),
    }


def _correo_de(usuario):
    return getattr(usuario, "correo_institucional", "") or usuario.email or ""


def _cuenta_servidor():
    """Cómo envía el portal cuando no hay cuenta activa (solo para mostrarlo)."""
    if "console" in settings.EMAIL_BACKEND_RESPALDO or "locmem" in settings.EMAIL_BACKEND_RESPALDO:
        return "Modo de prueba: los correos solo se muestran en la consola del servidor, no se envían."
    if settings.EMAIL_HOST_USER:
        return f"{settings.DEFAULT_FROM_EMAIL} (cuenta configurada en el servidor)"
    return "No hay una cuenta configurada en el servidor."


@coordinador_required
def correo_envio(request):
    """Configuración → Correo de envío."""
    guardada = config.obtener_configuracion()
    configuracion = guardada or ConfiguracionCorreo(
        pk=config.PK_CONFIGURACION,
        remitente_correo=_correo_de(request.user),
    )
    tiene_clave = bool(configuracion.clave_cifrada)
    accion = request.POST.get("accion") if request.method == "POST" else None

    form = ConfiguracionCorreoForm(
        request.POST if accion == "guardar" else None,
        instance=configuracion,
        tiene_clave=tiene_clave,
    )
    form_prueba = CorreoPruebaForm(
        request.POST if accion == "probar" else None,
        initial={"destinatario": _correo_de(request.user)},
    )

    if accion == "guardar" and form.is_valid():
        anteriores = _auditable(guardada)
        nueva = form.save(commit=False)
        clave_nueva = form.cleaned_data.get("clave")
        clave = clave_nueva or config.descifrar(configuracion.clave_cifrada)
        if clave_nueva:
            nueva.clave_cifrada = config.cifrar(clave_nueva)

        error = None
        if nueva.activo:
            # Nunca se activa una cuenta que no funciona: los correos seguirían saliendo mal.
            error = "Escribe la clave de aplicación otra vez." if not clave else config.probar_conexion(nueva, clave)
        if error:
            form.add_error(None, f"No se guardó: {error}")
        else:
            if nueva.activo:
                nueva.fecha_verificacion = timezone.now()
            nueva.modificado_por_usuario = request.user
            nueva.save()
            registrar_auditoria(
                request=request,
                entidad="ConfiguracionCorreo",
                entidad_id=nueva.pk,
                accion="CAMBIO_CORREO_ENVIO",
                valores_anteriores=anteriores,
                valores_nuevos=_auditable(nueva),
            )
            if nueva.activo:
                messages.success(request, f"Listo: los correos del portal saldrán desde {nueva.remitente_correo}.")
            else:
                messages.info(request, "Guardado. Los correos siguen saliendo con la cuenta del servidor.")
            return redirect("comunicaciones:correo_envio")

    if accion == "probar" and form_prueba.is_valid():
        destinatario = form_prueba.cleaned_data["destinatario"]
        envio = EnvioCorreo.objects.create(
            remitente=config.remitente_actual(),
            destinatario=destinatario,
            asunto="Correo de prueba del Portal A+S",
            cuerpo=(
                "Este es un correo de prueba enviado desde Configuración → Correo de envío.\n\n"
                "Si lo recibiste, los avisos, cartas y encuestas del portal llegarán desde esta misma cuenta."
            ),
            resultado="PENDIENTE",
            numero_intento=1,
        )
        try:
            EmailMessage(
                subject=envio.asunto, body=envio.cuerpo, from_email=envio.remitente,
                to=[destinatario], connection=get_connection(),
            ).send(fail_silently=False)
            envio.resultado, envio.fecha_envio = "OK", timezone.now()
            messages.success(request, f"Correo de prueba enviado a {destinatario}. Revisa también la carpeta de spam.")
        except Exception as error:  # noqa: BLE001 - se muestra al Coordinador
            envio.resultado, envio.detalle_error = "ERROR", str(error)
            messages.error(request, f"No se pudo enviar la prueba. {config.explicar_error(error)}")
        envio.save()
        return redirect("comunicaciones:correo_envio")

    activa, _ = config.configuracion_activa()
    return render(request, "comunicaciones/correo_envio.html", {
        "form": form,
        "form_prueba": form_prueba,
        "configuracion": guardada,
        "activa": activa,
        "clave_ilegible": bool(guardada and guardada.activo and guardada.clave_cifrada and activa is None),
        "remitente_actual": config.remitente_actual(),
        "cuenta_servidor": _cuenta_servidor(),
        "servidores": config.SERVIDORES,
    })
