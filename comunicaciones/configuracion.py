"""
Cuenta de envío elegida por el Coordinador (ConfiguracionCorreo).

- La clave de aplicación se guarda cifrada con Fernet (AES). La llave sale de
  CORREO_CLAVE_CIFRADO o, si no está, de SECRET_KEY. Si esa llave cambia, la
  clave guardada ya no se puede leer: el portal vuelve a la cuenta del
  servidor y el Coordinador solo debe escribir la clave otra vez.
- Ningún correo se pierde por una mala configuración: antes de activar una
  cuenta se prueba la conexión, y si la cuenta guardada no se puede usar se
  envía con la del servidor (.env / Render).
"""

import base64
import hashlib
import logging
import smtplib
import socket
from email.headerregistry import Address

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend

logger = logging.getLogger(__name__)


SERVIDORES = {
    "MICROSOFT": ("smtp.office365.com", 587, True),
    "GMAIL": ("smtp.gmail.com", 587, True),
}

PK_CONFIGURACION = 1


def _fernet():
    from cryptography.fernet import Fernet

    secreto = getattr(settings, "CORREO_CLAVE_CIFRADO", "") or settings.SECRET_KEY
    llave = hashlib.sha256(f"correo-portal-as:{secreto}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(llave))


def cifrar(texto):
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(texto):
    """Clave en claro, o None si no se puede leer (llave cambiada o dato dañado)."""
    from cryptography.fernet import InvalidToken

    if not texto:
        return None
    try:
        return _fernet().decrypt(texto.encode()).decode()
    except (InvalidToken, ValueError):
        logger.warning("No se pudo descifrar la clave del correo de envío; se usa la cuenta del servidor.")
        return None


def obtener_configuracion():
    """La fila de configuración (sin crearla), o None."""
    from .models import ConfiguracionCorreo

    return ConfiguracionCorreo.objects.filter(pk=PK_CONFIGURACION).first()


def configuracion_activa():
    """(configuración, clave) si hay una cuenta activa y usable; si no, (None, None)."""
    try:
        configuracion = obtener_configuracion()
    except Exception:
        logger.warning("No se pudo leer la configuración de correo.", exc_info=True)
        return None, None
    if configuracion is None or not configuracion.activo:
        return None, None
    clave = descifrar(configuracion.clave_cifrada)
    if not clave:
        return None, None
    return configuracion, clave


def remitente_de(configuracion):
    return str(Address(display_name=configuracion.remitente_nombre, addr_spec=configuracion.remitente_correo))


def remitente_actual():
    """Remitente que verán los destinatarios ("Nombre <correo>")."""
    configuracion, _ = configuracion_activa()
    if configuracion:
        return remitente_de(configuracion)
    return settings.DEFAULT_FROM_EMAIL


def conexion_smtp(configuracion, clave, fail_silently=False):
    return SmtpBackend(
        host=configuracion.servidor_smtp,
        port=configuracion.puerto,
        username=configuracion.remitente_correo,
        password=clave,
        use_tls=configuracion.usar_tls,
        fail_silently=fail_silently,
        timeout=20,
    )


def explicar_error(error):
    """Mensaje entendible para el Coordinador a partir del error de SMTP."""
    texto = str(error)
    if isinstance(error, smtplib.SMTPAuthenticationError):
        if "5.7.139" in texto or "SmtpClientAuthentication" in texto or "basic authentication is disabled" in texto.lower():
            return (
                "Tu cuenta Microsoft tiene bloqueado el envío por SMTP. Lo debe habilitar DTI "
                "(SMTP AUTH para esa cuenta). Mientras tanto se sigue usando la cuenta del servidor."
            )
        if "5.7.8" in texto or "Username and Password not accepted" in texto:
            return (
                "El correo o la clave no son correctos. En Gmail usa una contraseña de aplicación, "
                "no tu clave normal."
            )
        return "El servidor rechazó el usuario o la clave."
    if isinstance(error, (socket.timeout, TimeoutError, ConnectionError, socket.gaierror, OSError)) and not isinstance(
        error, smtplib.SMTPException
    ):
        return "No se pudo conectar con el servidor de correo. Revisa el servidor y el puerto."
    return f"El servidor de correo respondió: {texto[:200]}"


def probar_conexion(configuracion, clave):
    """Inicia sesión en el servidor SMTP. Devuelve None si funciona o el mensaje de error."""
    conexion = conexion_smtp(configuracion, clave)
    try:
        conexion.open()
    except Exception as error:
        return explicar_error(error)
    finally:
        try:
            conexion.close()
        except Exception:
            pass
    return None
