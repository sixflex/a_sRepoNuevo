from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class CargarHistoricosCommandTest(TestCase):
    def test_comando_sin_archivo_indica_pendiente(self):
        out = StringIO()
        call_command(
            "cargar_historicos",
            tipo="CARTAS_PRESENTACION",
            stdout=out,
        )
        salida = out.getvalue()
        self.assertIn("CARTAS_PRESENTACION", salida)
        self.assertIn("pendiente de recepción", salida)

    def test_comando_con_dry_run_sin_archivo(self):
        out = StringIO()
        call_command(
            "cargar_historicos",
            tipo="RESUMEN_DOCENTE",
            dry_run=True,
            stdout=out,
        )
        salida = out.getvalue()
        self.assertIn("RESUMEN_DOCENTE", salida)

    def test_comando_con_tipo_invalido_falla(self):
        with self.assertRaises(CommandError):
            call_command(
                "cargar_historicos",
                tipo="TIPO_INEXISTENTE",
            )