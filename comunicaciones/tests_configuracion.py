"""Configuración → Correo de envío: cuenta elegida por el Coordinador."""
import smtplib
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.mail import EmailMessage, get_connection, send_mail
from django.test import TestCase, override_settings
from django.urls import reverse

from auditoria.models import AuditoriaCambio

from . import configuracion as config
from .models import ConfiguracionCorreo, EnvioCorreo

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
BACKEND = "comunicaciones.backend.CorreoConfigurableBackend"


def _guardar(**extra):
    datos = dict(
        pk=1, remitente_nombre="Coordinación A+S", remitente_correo="jorge@cloud.uautonoma.cl",
        proveedor="MICROSOFT", servidor_smtp="smtp.office365.com", puerto=587, usar_tls=True,
        clave_cifrada=config.cifrar("clave-app"), activo=True,
    )
    datos.update(extra)
    return ConfiguracionCorreo.objects.create(**datos)


class CifradoTests(TestCase):
    def test_la_clave_no_queda_en_claro_y_se_recupera(self):
        cifrada = config.cifrar("mi-clave")
        self.assertNotIn("mi-clave", cifrada)
        self.assertEqual(config.descifrar(cifrada), "mi-clave")

    def test_si_cambia_la_llave_vuelve_a_la_cuenta_del_servidor(self):
        _guardar()
        with override_settings(SECRET_KEY="otra-llave-distinta"), self.assertLogs("comunicaciones.configuracion", "WARNING"):
            self.assertEqual(config.configuracion_activa(), (None, None))


@override_settings(EMAIL_BACKEND=BACKEND, EMAIL_BACKEND_RESPALDO=LOCMEM, DEFAULT_FROM_EMAIL="Servidor <srv@uautonoma.cl>")
class BackendTests(TestCase):
    def test_sin_configuracion_usa_el_backend_del_servidor(self):
        send_mail("Hola", "x", None, ["a@uautonoma.cl"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "Servidor <srv@uautonoma.cl>")
        self.assertEqual(config.remitente_actual(), "Servidor <srv@uautonoma.cl>")

    def test_desactivada_usa_el_servidor(self):
        _guardar(activo=False)
        send_mail("Hola", "x", None, ["a@uautonoma.cl"])
        self.assertEqual(len(mail.outbox), 1)

    @patch("comunicaciones.configuracion.SmtpBackend")
    def test_activa_envia_con_esa_cuenta_y_ese_remitente(self, smtp):
        _guardar(responder_a="as@uautonoma.cl")
        smtp.return_value.send_messages.side_effect = lambda mensajes: len(mensajes)
        mensaje = EmailMessage("Hola", "x", "Servidor <srv@uautonoma.cl>", ["a@uautonoma.cl"])
        self.assertEqual(get_connection().send_messages([mensaje]), 1)
        kwargs = smtp.call_args.kwargs
        self.assertEqual((kwargs["host"], kwargs["username"], kwargs["password"]),
                         ("smtp.office365.com", "jorge@cloud.uautonoma.cl", "clave-app"))
        self.assertEqual(mensaje.from_email, "Coordinación A+S <jorge@cloud.uautonoma.cl>")
        self.assertEqual(mensaje.reply_to, ["as@uautonoma.cl"])
        self.assertEqual(config.remitente_actual(), "Coordinación A+S <jorge@cloud.uautonoma.cl>")


@override_settings(EMAIL_BACKEND=BACKEND, EMAIL_BACKEND_RESPALDO=LOCMEM)
class PantallaCorreoTests(TestCase):
    def setUp(self):
        self.coordinador = get_user_model().objects.create_user(
            username="jorge", password="x", email="jorge@cloud.uautonoma.cl")
        self.coordinador.groups.add(Group.objects.get_or_create(name="Coordinador")[0])
        self.client.force_login(self.coordinador)
        self.url = reverse("comunicaciones:correo_envio")

    def guardar(self, **extra):
        datos = {
            "accion": "guardar", "remitente_nombre": "Coordinación A+S",
            "remitente_correo": "Jorge@cloud.uautonoma.cl", "responder_a": "", "proveedor": "MICROSOFT",
            "servidor_smtp": "", "puerto": "587", "usar_tls": "on", "activo": "on", "clave": "clave-app",
        }
        datos.update(extra)
        return self.client.post(self.url, {k: v for k, v in datos.items() if v is not None})

    def test_pantalla_muestra_desde_donde_salen_hoy(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Hoy los correos del portal salen desde")
        self.assertContains(respuesta, "Configuración")

    @patch("comunicaciones.configuracion.probar_conexion", return_value=None)
    def test_guardar_prueba_la_conexion_cifra_y_audita(self, probar):
        self.assertRedirects(self.guardar(), self.url)
        guardada = ConfiguracionCorreo.objects.get()
        self.assertTrue(guardada.activo)
        self.assertEqual(guardada.remitente_correo, "jorge@cloud.uautonoma.cl")
        self.assertEqual(guardada.servidor_smtp, "smtp.office365.com")  # completado por el proveedor
        self.assertNotIn("clave-app", guardada.clave_cifrada)
        self.assertEqual(config.descifrar(guardada.clave_cifrada), "clave-app")
        self.assertIsNotNone(guardada.fecha_verificacion)
        probar.assert_called_once()
        auditoria = AuditoriaCambio.objects.get(accion="CAMBIO_CORREO_ENVIO")
        self.assertNotIn("clave-app", str(auditoria.valores_nuevos_json))
        self.assertTrue(auditoria.valores_nuevos_json["tiene_clave"])

    @patch("comunicaciones.configuracion.SmtpBackend")
    def test_si_la_conexion_falla_no_se_guarda_nada(self, smtp):
        smtp.return_value.open.side_effect = smtplib.SMTPAuthenticationError(
            535, b"5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled for the Tenant.")
        respuesta = self.guardar()
        self.assertContains(respuesta, "bloqueado el envío por SMTP")
        self.assertFalse(ConfiguracionCorreo.objects.exists())

    @patch("comunicaciones.configuracion.probar_conexion", return_value=None)
    def test_la_clave_no_se_muestra_y_en_blanco_se_mantiene(self, _):
        self.guardar()
        respuesta = self.client.get(self.url)
        self.assertNotContains(respuesta, "clave-app")
        self.assertContains(respuesta, "Ya hay una clave guardada")
        self.guardar(clave="", remitente_nombre="A+S")
        guardada = ConfiguracionCorreo.objects.get()
        self.assertEqual(guardada.remitente_nombre, "A+S")
        self.assertEqual(config.descifrar(guardada.clave_cifrada), "clave-app")

    def test_activar_sin_clave_pide_la_clave(self):
        self.assertContains(self.guardar(clave=""), "Escribe la clave de aplicación")
        self.assertFalse(ConfiguracionCorreo.objects.exists())

    def test_desactivar_no_necesita_probar(self):
        self.assertRedirects(self.guardar(activo=None, clave=""), self.url)
        self.assertFalse(ConfiguracionCorreo.objects.get().activo)

    def test_otro_servidor_pide_el_servidor(self):
        self.assertContains(self.guardar(proveedor="OTRO", activo=None), "Indica el servidor SMTP")

    def test_correo_de_prueba_queda_registrado(self):
        respuesta = self.client.post(self.url, {"accion": "probar", "destinatario": "binya@uautonoma.cl"})
        self.assertRedirects(respuesta, self.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EnvioCorreo.objects.get().resultado, "OK")

    def test_solo_coordinacion(self):
        docente = get_user_model().objects.create_user(username="doc", password="x")
        docente.groups.add(Group.objects.get_or_create(name="Docente")[0])
        self.client.force_login(docente)
        self.assertEqual(self.client.get(self.url).status_code, 403)


class ExplicarErrorTests(TestCase):
    def test_gmail_clave_incorrecta(self):
        error = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
        self.assertIn("contraseña de aplicación", config.explicar_error(error))

    def test_sin_conexion(self):
        self.assertIn("No se pudo conectar", config.explicar_error(TimeoutError("timed out")))
