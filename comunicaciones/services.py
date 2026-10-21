from django.conf import settings
from django.core.mail import EmailMessage
from django.template import Context, Template
from django.utils import timezone
from archivos.services import abrir_archivo
from comunicaciones.models import EnvioCorreo, PlantillaCorreo


class EmailService:
    @staticmethod
    def enviar_correo(
        codigo_plantilla: str,
        destinatario: str,
        contexto: dict,
        remitente: str = None,
        carta_documento=None,
        postulacion=None,
        invitacion_cierre=None,
    ) -> EnvioCorreo:
        """
        Servicio comun para preparar y enviar correos usando PlantillaCorreo.
        Registra el intento en EnvioCorreo indicando exito o fallo.
        """
        remitente_final = remitente or settings.DEFAULT_FROM_EMAIL

        
        try:
            plantilla = PlantillaCorreo.objects.get(codigo=codigo_plantilla, activo=True)
            asunto_renderizado = Template(plantilla.asunto_template).render(Context(contexto))
            cuerpo_renderizado = Template(plantilla.cuerpo_template).render(Context(contexto))
        except PlantillaCorreo.DoesNotExist as e:
           
            return EnvioCorreo.objects.create(
                plantilla=None,
                carta_documento=carta_documento,
                postulacion=postulacion,
                invitacion_cierre=invitacion_cierre,
                remitente=remitente_final,
                destinatario=destinatario,
                asunto=f"ERROR: Plantilla {codigo_plantilla} no encontrada",
                cuerpo="",
                fecha_envio=None,
                resultado="ERROR",
                detalle_error=f"No existe plantilla activa con código: {codigo_plantilla}",
                numero_intento=1,
            )

        
        envio = EnvioCorreo.objects.create(
            plantilla=plantilla,
            carta_documento=carta_documento,
            postulacion=postulacion,
            invitacion_cierre=invitacion_cierre,
            remitente=remitente_final,
            destinatario=destinatario,
            asunto=asunto_renderizado,
            cuerpo=cuerpo_renderizado,
            fecha_envio=None,
            resultado="PENDIENTE",
            detalle_error=None,
            numero_intento=1,
        )

       
        return EmailService._ejecutar_envio(envio)

    @staticmethod
    def reintentar_envio(envio_id: int) -> EnvioCorreo:
        """
        Reintenta un correo fallido o pendiente existente sin duplicar la operacion funcional original.
        """
        envio = EnvioCorreo.objects.get(pk=envio_id)
        if envio.resultado == "OK":
            return envio
        envio.numero_intento += 1
        return EmailService._ejecutar_envio(envio)

    @staticmethod
    def _ejecutar_envio(envio: EnvioCorreo) -> EnvioCorreo:
        """Metodo privado que envia el correo (con el PDF de la carta si corresponde) y actualiza el resultado."""
        try:
            correo = EmailMessage(
                subject=envio.asunto,
                body=envio.cuerpo,
                from_email=envio.remitente,
                to=[envio.destinatario],
            )
            if envio.carta_documento_id:
                archivo = envio.carta_documento.archivo
                with abrir_archivo(archivo) as contenido:
                    correo.attach(archivo.nombre_original, contenido.read(), archivo.mime_type)
            correo.send(fail_silently=False)
            envio.resultado = "OK"
            envio.detalle_error = None
        except Exception as ex:
            envio.resultado = "ERROR"
            envio.detalle_error = str(ex)

        # Fecha del ultimo intento, tambien cuando falla (RF-CAR-08).
        envio.fecha_envio = timezone.now()

        envio.save()
        return envio
