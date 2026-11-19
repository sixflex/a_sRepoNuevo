from comunicaciones.configuracion import remitente_actual
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone


def construir_url_planificacion(request, enlace):
    ruta = reverse(
        "planificacion:formulario_tabular_as",
        kwargs={"token": enlace.token},
    )
    return request.build_absolute_uri(ruta)

def enviar_correo_planificacion(request, enlace, reenvio=False):
    url = construir_url_planificacion(
        request,
        enlace,
    )

    if reenvio:
        asunto = "Reenvío de planificación académica A+S"
        introduccion = (
            "Se reenvía el enlace de planificación académica A+S."
        )
    else:
        asunto = "Solicitud de planificación académica A+S"
        introduccion = (
            "Se ha generado una solicitud de planificación "
            "académica A+S."
        )

    # La vigencia se muestra en hora de Chile, no en UTC.
    expiracion = (
        timezone.localtime(enlace.fecha_expiracion).strftime("%d/%m/%Y %H:%M")
        if enlace.fecha_expiracion
        else "Sin fecha de expiración definida"
    )

    mensaje = (
        f"Estimado/a {enlace.destinatario_nombre}:\n\n"
        f"{introduccion}\n\n"
        f"Unidad académica: {enlace.unidad_academica}\n"
        f"Campus: {enlace.campus}\n"
        f"Período: {enlace.periodo}\n"
        f"Vigencia: {expiracion}\n\n"
        f"Enlace de planificación:\n{url}\n\n"
        "Este enlace corresponde a su unidad. Si otra persona debe completar "
        "la planificación, puede reenviárselo bajo su responsabilidad.\n\n"
        "Portal A+S"
    )

    remitente = remitente_actual()

    enviados = send_mail(
        subject=asunto,
        message=mensaje,
        from_email=remitente,
        recipient_list=[enlace.destinatario_correo],
        fail_silently=False,
    )

    return enviados == 1

def enviar_correo_devolucion(request, enlace, motivo):
    """Avisa a Dirección que la Coordinación devolvió la planificación, con el motivo y el enlace."""
    url = construir_url_planificacion(request, enlace)
    expiracion = (
        timezone.localtime(enlace.fecha_expiracion).strftime("%d/%m/%Y %H:%M")
        if enlace.fecha_expiracion
        else "Sin fecha de expiración definida"
    )
    mensaje = (
        f"Estimado/a {enlace.destinatario_nombre}:\n\n"
        "La Coordinación A+S revisó la planificación académica A+S enviada y "
        "la devolvió para que sea corregida.\n\n"
        f"Motivo:\n{motivo}\n\n"
        f"Unidad académica: {enlace.unidad_academica}\n"
        f"Campus: {enlace.campus}\n"
        f"Período: {enlace.periodo}\n"
        f"Vigencia del enlace: {expiracion}\n\n"
        "Puede corregirla en el mismo enlace y volver a usar «Enviar versión final»:\n"
        f"{url}\n\n"
        "Portal A+S"
    )
    enviados = send_mail(
        subject="Planificación académica A+S devuelta para corrección",
        message=mensaje,
        from_email=remitente_actual(),
        recipient_list=[enlace.destinatario_correo],
        fail_silently=False,
    )
    return enviados == 1
