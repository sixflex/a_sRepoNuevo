from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


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

    expiracion = (
        enlace.fecha_expiracion.strftime("%d/%m/%Y %H:%M")
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
        "Este enlace es individual. No debe ser compartido.\n\n"
        "Portal A+S"
    )

    remitente = getattr(
        settings,
        "DEFAULT_FROM_EMAIL",
        None,
    )

    enviados = send_mail(
        subject=asunto,
        message=mensaje,
        from_email=remitente,
        recipient_list=[enlace.destinatario_correo],
        fail_silently=False,
    )

    return enviados == 1