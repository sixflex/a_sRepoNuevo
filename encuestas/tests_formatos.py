from io import StringIO
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from encuestas import formatos
from socios.models import Comuna


class TelefonoTests(SimpleTestCase):
    def test_formatos_aceptados(self):
        for texto in ("+56912345678", "9 1234 5678", "56 9 1234-5678", "912345678"):
            self.assertEqual(formatos.telefono(texto), "+56 9 1234 5678")

    def test_fijo_y_varios_numeros(self):
        self.assertEqual(formatos.telefono("412345678 / 912345678"), "+56 41 234 5678 / +56 9 1234 5678")

    def test_invalido(self):
        with self.assertRaises(ValidationError):
            formatos.telefono("12345")


class DeducirTests(SimpleTestCase):
    def test_por_texto_de_la_pregunta(self):
        self.assertEqual(formatos.deducir("Comuna del socio"), formatos.COMUNA)
        self.assertEqual(formatos.deducir("Teléfono de contacto"), formatos.TELEFONO)
        self.assertEqual(formatos.deducir("Carrera"), formatos.CARRERA)
        self.assertEqual(formatos.deducir("Nombre de la asignatura"), formatos.ASIGNATURA)
        self.assertEqual(formatos.deducir("Nombre de la organización"), formatos.LIBRE)


class ComunaTests(TestCase):
    def test_catalogo_idempotente_y_reusa_existente(self):
        Comuna.objects.create(nombre="la florida", region="", activo=True)
        call_command("cargar_catalogos_socios", stdout=StringIO())
        call_command("cargar_catalogos_socios", stdout=StringIO())
        self.assertEqual(Comuna.objects.filter(nombre__iexact="la florida").count(), 1)
        self.assertGreaterEqual(Comuna.objects.count(), 346)

    def test_comuna_estricta_con_catalogo(self):
        catalogos = {formatos.COMUNA: ["La Florida", "Ñuñoa"]}
        self.assertEqual(formatos.normalizar(formatos.COMUNA, "  LA  florida ", catalogos), "La Florida")
        self.assertEqual(formatos.normalizar(formatos.COMUNA, "nunoa", catalogos), "Ñuñoa")
        with self.assertRaises(ValidationError):
            formatos.normalizar(formatos.COMUNA, "Gótica", catalogos)
