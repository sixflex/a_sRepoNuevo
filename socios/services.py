from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from comunicaciones.models import EnvioCorreo

def enviar_notificacion_postulacion(postulacion, tipo_evento, motivo=None):
    """
    Envía notificación y registra la auditoría en EnvioCorreo (CDE-55, CDE-56).
    """
    correo_destinatario = None
    if hasattr(postulacion, "respuesta_formulario") and postulacion.respuesta_formulario:
        correo_destinatario = postulacion.respuesta_formulario.respondente_correo

    if not correo_destinatario and postulacion.socio:
        contacto = postulacion.socio.contactos.filter(es_principal=True, activo=True).first()
        if contacto:
            correo_destinatario = contacto.correo

    if not correo_destinatario:
        return None

    if tipo_evento == "RECEPCION":
        asunto = f"Confirmación de Postulación A+S - Folio #{postulacion.id}"
        cuerpo = (
            f"Estimado(a) postulante,\n\n"
            f"Confirmamos la recepción de su postulación a la convocatoria "
            f"'{postulacion.convocatoria.nombre}'.\n"
            f"Identificador de seguimiento: #{postulacion.id}\n"
            f"Fecha de recepción: {postulacion.fecha_recepcion.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"El equipo de Coordinación A+S revisará sus antecedentes."
        )
    elif tipo_evento == "APROBADA":
        asunto = f"Postulación A+S Aprobada - Folio #{postulacion.id}"
        cuerpo = (
            f"Estimado(a) Socio Comunitario,\n\n"
            f"Nos complace informarle que su postulación a la convocatoria "
            f"'{postulacion.convocatoria.nombre}' ha sido APROBADA.\n\n"
            f"Pronto un docente o coordinador se contactará con usted para coordinar el trabajo conjunto."
        )
    elif tipo_evento == "RECHAZADA":
        asunto = f"Estado de Postulación A+S - Folio #{postulacion.id}"
        cuerpo = (
            f"Estimado(a) postulante,\n\n"
            f"Le informamos que su postulación a la convocatoria "
            f"'{postulacion.convocatoria.nombre}' no ha sido seleccionada en esta oportunidad.\n\n"
            f"Motivo institucional:\n{motivo or 'Sin motivo especificado.'}\n\n"
            f"Agradecemos su interés en el programa de Aprendizaje + Servicio."
        )
    else:
        return None

    remitente = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@uautonoma.cl")
    resultado = "PENDIENTE"
    detalle_error = None

    try:
        send_mail(
            asunto,
            cuerpo,
            remitente,
            [correo_destinatario],
            fail_silently=False,
        )
        resultado = "OK"
    except Exception as exc:
        resultado = "ERROR"
        detalle_error = str(exc)

    registro = EnvioCorreo.objects.create(
        postulacion=postulacion,
        remitente=remitente,
        destinatario=correo_destinatario,
        asunto=asunto,
        cuerpo=cuerpo,
        fecha_envio=timezone.now(),
        resultado=resultado,
        detalle_error=detalle_error,
        numero_intento=1,
    )
    return registro