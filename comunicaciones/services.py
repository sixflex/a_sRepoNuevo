from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template
from django.utils import timezone
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

        # 1. Obtener la plantilla activa
        try:
            plantilla = PlantillaCorreo.objects.get(codigo=codigo_plantilla, activo=True)
            asunto_renderizado = Template(plantilla.asunto_template).render(Context(contexto))
            cuerpo_renderizado = Template(plantilla.cuerpo_template).render(Context(contexto))
        except PlantillaCorreo.DoesNotExist as e:
            # Si no existe la plantilla, se deja registro del fallo
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

        # 2. Crear registro inicial en estado PENDIENTE
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

        # 3. Intentar el envío por SMTP / Backend activo
        return EmailService._ejecutar_envio(envio)

    @staticmethod
    def reintentar_envio(envio_id: int) -> EnvioCorreo:
        """
        Reintenta un correo fallido o pendiente existente sin duplicar la operacion funcional original.
        """
        envio = EnvioCorreo.objects.get(pk=envio_id)
        envio.numero_intento += 1
        return EmailService._ejecutar_envio(envio)

    @staticmethod
    def _ejecutar_envio(envio: EnvioCorreo) -> EnvioCorreo:
        """Metodo privado que ejecuta send_mail y actualiza el resultado."""
        try:
            send_mail(
                subject=envio.asunto,
                message=envio.cuerpo,
                from_email=envio.remitente,
                recipient_list=[envio.destinatario],
                fail_silently=False,
            )
            envio.resultado = "OK"
            envio.fecha_envio = timezone.now()
            envio.detalle_error = None
        except Exception as ex:
            envio.resultado = "ERROR"
            envio.detalle_error = str(ex)
        
        envio.save()
        return envio