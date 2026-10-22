import tempfile
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from PIL import Image as PilImage

from cartas import services

MARCA_IMAGEN = b"/Subtype /Image"


def _crear_firma(directorio):
    ruta = Path(directorio) / "firma_prueba.png"
    PilImage.new("RGB", (400, 150), "navy").save(ruta)
    return ruta


def _solicitud_falsa():
    solicitud = MagicMock()
    solicitud.id = 7
    solicitud.estado = "APROBADA"
    solicitud.fecha_aprobacion = datetime(2026, 10, 1, tzinfo=dt_timezone.utc)
    solicitud.docente_derivador = SimpleNamespace(nombres="Ana", apellidos="Pérez")
    solicitud.seccion.asignatura.nombre = "Taller de Servicio"
    solicitud.persona_receptora = "María Soto"
    solicitud.institucion_receptora = "Junta de Vecinos"
    solicitud.consideraciones = ""
    solicitud.documentos.order_by.return_value.values_list.return_value.first.return_value = None
    return solicitud


def _generar_pdf():
    """Ejecuta generar_pdf_carta real y devuelve los bytes del PDF."""
    estudiantes = [SimpleNamespace(nombre="Luis Rojas", rut="11.111.111-1")]
    usuario = SimpleNamespace(get_full_name=lambda: "Coordinador", username="coord")
    with patch.object(services, "guardar_archivo") as guardar, \
            patch.object(services, "CartaDocumento"), \
            patch.object(services, "transaction"):
        services.generar_pdf_carta(_solicitud_falsa(), usuario, estudiantes)
    return guardar.call_args.args[0].read()


class FirmaPruebaCartaTests(SimpleTestCase):
    def test_pdf_aprobado_incluye_la_firma_si_esta_configurada(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = _crear_firma(tmp)
            with override_settings(CARTA_FIRMA_PRUEBA_PATH=str(ruta)):
                pdf = _generar_pdf()
        self.assertIn(MARCA_IMAGEN, pdf)

    def test_sin_configuracion_el_pdf_se_genera_sin_firma(self):
        with override_settings(CARTA_FIRMA_PRUEBA_PATH=""):
            pdf = _generar_pdf()
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertNotIn(MARCA_IMAGEN, pdf)

    def test_ruta_inexistente_no_rompe_la_generacion(self):
        with override_settings(CARTA_FIRMA_PRUEBA_PATH="/no/existe/firma.png"):
            with self.assertLogs("cartas.services", level="WARNING"):
                pdf = _generar_pdf()
        self.assertNotIn(MARCA_IMAGEN, pdf)

    def test_archivo_que_no_es_imagen_no_rompe_la_generacion(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "firma.png"
            ruta.write_bytes(b"no soy una imagen")
            with override_settings(CARTA_FIRMA_PRUEBA_PATH=str(ruta)):
                with self.assertLogs("cartas.services", level="WARNING"):
                    pdf = _generar_pdf()
        self.assertNotIn(MARCA_IMAGEN, pdf)

    def test_la_firma_no_esta_en_rutas_publicas(self):
        """La imagen no puede estar en static ni en media (no accesible por URL)."""
        with tempfile.TemporaryDirectory() as tmp:
            ruta = _crear_firma(tmp).resolve()
            with override_settings(CARTA_FIRMA_PRUEBA_PATH=str(ruta)):
                publicas = [
                    getattr(settings, "STATIC_ROOT", None),
                    getattr(settings, "MEDIA_ROOT", None),
                    *getattr(settings, "STATICFILES_DIRS", []),
                ]
                for carpeta in filter(None, publicas):
                    self.assertNotIn(Path(carpeta).resolve(), ruta.parents)
