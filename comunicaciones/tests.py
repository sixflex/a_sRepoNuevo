from io import StringIO
from unittest.mock import patch
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from comunicaciones.models import EnvioCorreo, PlantillaCorreo
from comunicaciones.services import EmailService


class EmailServiceTestCase(TestCase):
    def setUp(self):
        self.plantilla = PlantillaCorreo.objects.create(
            codigo="BIENVENIDA_SOCIO",
            asunto_template="Bienvenido {{ nombre }}",
            cuerpo_template="Hola {{ nombre }}, tu proyecto es {{ proyecto }}.",
            activo=True,
        )

    def test_envio_exitoso(self):
        envio = EmailService.enviar_correo(
            codigo_plantilla="BIENVENIDA_SOCIO",
            destinatario="socio@comunidad.cl",
            contexto={"nombre": "Juan", "proyecto": "Fondo Concursable"},
        )

        self.assertEqual(envio.resultado, "OK")
        self.assertIsNotNone(envio.fecha_envio)
        self.assertEqual(envio.asunto, "Bienvenido Juan")
        self.assertIn("Fondo Concursable", envio.cuerpo)
        self.assertEqual(len(mail.outbox), 1)

    def test_envio_destinatario_invalido_falla(self):
        """CDE-345: Validar que una dirección con formato incorrecto registre error sin enviar."""
        envio = EmailService.enviar_correo(
            codigo_plantilla="BIENVENIDA_SOCIO",
            destinatario="correo-invalido-sin-arroba",
            contexto={"nombre": "Juan"},
        )

        self.assertEqual(envio.resultado, "ERROR")
        self.assertIn("no tiene un formato válido", envio.detalle_error)

    @patch("comunicaciones.services.send_mail")
    def test_envio_fallido_registra_error(self, mock_send_mail):
        """CDE-347: Simular un fallo de conexión SMTP."""
        mock_send_mail.side_effect = Exception("Fallo de conexión SMTP")

        envio = EmailService.enviar_correo(
            codigo_plantilla="BIENVENIDA_SOCIO",
            destinatario="socio@comunidad.cl",
            contexto={"nombre": "Juan", "proyecto": "Fondo Concursable"},
        )

        self.assertEqual(envio.resultado, "ERROR")
        self.assertIn("Fallo de conexión SMTP", envio.detalle_error)
        self.assertEqual(envio.numero_intento, 1)

    @patch("comunicaciones.services.send_mail")
    def test_reintento_no_duplica_registro(self, mock_send_mail):
        """CDE-348: Validar reintento sobre el mismo correo sin duplicar registros en BD."""
        mock_send_mail.side_effect = Exception("Fallo inicial")

        envio_inicial = EmailService.enviar_correo(
            codigo_plantilla="BIENVENIDA_SOCIO",
            destinatario="socio@comunidad.cl",
            contexto={"nombre": "Juan", "proyecto": "Test"},
        )
        self.assertEqual(EnvioCorreo.objects.count(), 1)

        mock_send_mail.side_effect = None
        envio_reintentado = EmailService.reintentar_envio(envio_inicial.id)

        self.assertEqual(EnvioCorreo.objects.count(), 1)
        self.assertEqual(envio_reintentado.resultado, "OK")
        self.assertEqual(envio_reintentado.numero_intento, 2)

    def test_command_probar_correo(self):
        """CDE-344: Validar ejecución del management command."""
        out = StringIO()
        call_command("probar_correo", destinatario="prueba@uautonoma.cl", stdout=out)
        salida = out.getvalue()
        self.assertIn("Envío EXITOSO", salida)