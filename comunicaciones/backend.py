"""
Backend de correo del portal (settings.EMAIL_BACKEND).

Todos los envíos (send_mail, EmailMessage, EmailService) pasan por aquí:
- si el Coordinador activó una cuenta en Configuración → Correo de envío, se
  envía con esa cuenta y ese remitente;
- si no, con el backend del servidor (EMAIL_BACKEND_RESPALDO: SMTP del .env o
  consola en desarrollo).
Así no hay que cambiar cada lugar que envía correos.
"""

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

from . import configuracion as config


class CorreoConfigurableBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.configuracion, clave = config.configuracion_activa()
        if self.configuracion:
            self.real = config.conexion_smtp(self.configuracion, clave, fail_silently=fail_silently)
        else:
            self.real = get_connection(
                settings.EMAIL_BACKEND_RESPALDO, fail_silently=fail_silently, **kwargs
            )

    def open(self):
        return self.real.open()

    def close(self):
        return self.real.close()

    def send_messages(self, email_messages):
        if self.configuracion:
            remitente = config.remitente_de(self.configuracion)
            for mensaje in email_messages:

                mensaje.from_email = remitente
                if self.configuracion.responder_a and not mensaje.reply_to:
                    mensaje.reply_to = [self.configuracion.responder_a]
        return self.real.send_messages(email_messages)
