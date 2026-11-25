"""
Carta con el formato oficial (cartas/plantilla_oficial.py).

La planilla Word de prueba se arma en memoria con imágenes de colores: así no
hay ninguna firma real en el repositorio (RN-07).
"""

import re
import tempfile
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings
from PIL import Image as PilImage

from reportlab import rl_config

from cartas import plantilla_oficial


def setUpModule():

    global _COMPRESION
    _COMPRESION = rl_config.pageCompression
    rl_config.pageCompression = 0


def tearDownModule():
    rl_config.pageCompression = _COMPRESION

ESTUDIANTES = [("Luis Rojas", "11.111.111-1"), ("Ana Soto", "22.222.222-2")]


def _png(color, tamano=(400, 150)):
    salida = BytesIO()
    PilImage.new("RGB", tamano, color).save(salida, format="PNG")
    return salida.getvalue()


def _planilla_docx(con_encabezado=True, imagenes_cuerpo=2):
    """Un .docx mínimo con logo en el encabezado y firma + tarjeta en el cuerpo."""
    colores = ["navy", "green", "purple"][:imagenes_cuerpo]
    recorte_firma = '<a:srcRect l="10000"/>'
    blips = "".join(
        f'<w:p><w:r><w:drawing><pic:blipFill><a:blip r:embed="rIdImg{i}"/>'
        f'{recorte_firma if i == 0 else ""}</pic:blipFill></w:drawing></w:r></w:p>'
        for i in range(len(colores))
    )
    rels_doc = "".join(
        f'<Relationship Id="rIdImg{i}" Type="image" Target="media/cuerpo{i}.png"/>'
        for i in range(len(colores))
    )
    salida = BytesIO()
    with zipfile.ZipFile(salida, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", f"<w:document><w:body>{blips}</w:body></w:document>")
        zf.writestr("word/_rels/document.xml.rels", f"<Relationships>{rels_doc}</Relationships>")
        for i, color in enumerate(colores):
            zf.writestr(f"word/media/cuerpo{i}.png", _png(color))
        if con_encabezado:
            zf.writestr("word/header1.xml", '<w:hdr><a:blip r:embed="rIdLogo"/></w:hdr>')
            zf.writestr(
                "word/_rels/header1.xml.rels",
                '<Relationships><Relationship Id="rIdLogo" Type="image" Target="media/logo.png"/></Relationships>',
            )
            zf.writestr("word/media/logo.png", _png("red", (300, 230)))
    return salida.getvalue()


def _texto_pdf(pdf):
    """Texto de las páginas del PDF (generado sin compresión en estas pruebas)."""
    return pdf.decode("latin-1")


def _imagenes_pdf(pdf):
    return len(re.findall(rb"/Subtype /Image", pdf))


def _pdf(borrador, recursos, proteger=False):
    return plantilla_oficial.construir_pdf(
        fecha=date(2026, 9, 2),
        persona_receptora="María Soto",
        institucion_receptora="Junta de Vecinos <Norte>",
        asignatura="Taller de Servicio",
        docente="Ana Pérez",
        estudiantes=ESTUDIANTES,
        borrador=borrador,
        recursos=recursos,
        proteger=proteger,
    )


class LeerPlanillaTests(SimpleTestCase):
    def test_saca_logo_firma_y_tarjeta_en_orden(self):
        imagenes = plantilla_oficial.leer_imagenes_planilla(_planilla_docx())
        self.assertIsNotNone(imagenes["logo"])
        self.assertIsNotNone(imagenes["tarjeta"])

        self.assertEqual(PilImage.open(BytesIO(imagenes["firma"])).size, (360, 150))
        self.assertEqual(PilImage.open(BytesIO(imagenes["tarjeta"])).getpixel((5, 5))[:3], (0, 128, 0))

    def test_planilla_sin_tarjeta_deja_la_tarjeta_vacia(self):
        imagenes = plantilla_oficial.leer_imagenes_planilla(_planilla_docx(imagenes_cuerpo=1))
        self.assertIsNotNone(imagenes["firma"])
        self.assertIsNone(imagenes["tarjeta"])

    def test_archivo_que_no_es_word_avisa(self):
        with self.assertRaises(ValueError):
            plantilla_oficial.leer_imagenes_planilla(b"no soy un docx")


class RecursosCartaTests(SimpleTestCase):
    """Respaldo cuando no hay carta oficial subida: no toca la BD."""

    def test_usa_la_planilla_configurada(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "carta.docx"
            ruta.write_bytes(_planilla_docx())
            with override_settings(CARTA_PLANTILLA_PATH=str(ruta), CARTA_FIRMA_PRUEBA_PATH=""):
                recursos = plantilla_oficial.recursos_carta(None)
        self.assertTrue(all(recursos[k] for k in ("logo", "firma", "tarjeta")))

    def test_sin_planilla_usa_la_firma_de_prueba_y_el_logo_del_portal(self):
        with tempfile.TemporaryDirectory() as tmp:
            firma = Path(tmp) / "firma.png"
            contenido = _png("navy")
            firma.write_bytes(contenido)
            with override_settings(CARTA_PLANTILLA_PATH="", CARTA_FIRMA_PRUEBA_PATH=str(firma)):
                recursos = plantilla_oficial.recursos_carta(None)
        self.assertEqual(recursos["firma"], contenido)
        self.assertIsNotNone(recursos["logo"])
        self.assertIsNone(recursos["tarjeta"])

    def test_planilla_inexistente_no_rompe(self):
        with override_settings(CARTA_PLANTILLA_PATH="/no/existe/carta.docx", CARTA_FIRMA_PRUEBA_PATH=""):
            with self.assertLogs("cartas.plantilla_oficial", level="WARNING"):
                recursos = plantilla_oficial.recursos_carta(None)
        self.assertIsNone(recursos["firma"])

    def test_la_planilla_no_esta_en_rutas_publicas(self):
        """La planilla trae la firma real: no puede quedar en static ni en media."""
        ruta = getattr(settings, "CARTA_PLANTILLA_PATH", "")
        if not ruta:
            self.skipTest("Sin planilla configurada en este entorno.")
        publicas = [
            getattr(settings, "STATIC_ROOT", None),
            getattr(settings, "MEDIA_ROOT", None),
            *getattr(settings, "STATICFILES_DIRS", []),
            settings.BASE_DIR,
        ]
        for carpeta in filter(None, publicas):
            self.assertNotIn(Path(carpeta).resolve(), Path(ruta).resolve().parents)


class PdfCartaTests(SimpleTestCase):
    def setUp(self):
        self.recursos = plantilla_oficial.leer_imagenes_planilla(_planilla_docx())

    def test_carta_final_lleva_texto_oficial_logo_firma_y_tarjeta(self):
        pdf = _pdf(borrador=False, recursos=self.recursos)
        texto = _texto_pdf(pdf)
        self.assertEqual(_imagenes_pdf(pdf), 3)
        self.assertIn("CARTA PRESENTACI", texto)
        self.assertIn("Santiago, 2 de septiembre de 2026", texto)
        self.assertIn("Por cualquier consulta o requerimiento", texto)
        self.assertIn("Luis Rojas", texto)
        self.assertIn("22.222.222-2", texto)

    def test_carta_final_no_lleva_marca_de_agua_ni_codigo_de_verificacion(self):
        texto = _texto_pdf(_pdf(borrador=False, recursos=self.recursos))
        self.assertNotIn("BORRADOR", texto)
        self.assertNotIn("Verificaci", texto)
        self.assertNotIn("APRENDIZAJE + SERVICIO", texto)

    def test_borrador_no_lleva_firma_y_se_marca_como_borrador(self):
        pdf = _pdf(borrador=True, recursos=self.recursos)
        self.assertEqual(_imagenes_pdf(pdf), 1)
        self.assertIn("BORRADOR", _texto_pdf(pdf))

    def test_sin_firma_ni_tarjeta_firma_coordinacion_en_texto(self):
        pdf = _pdf(borrador=False, recursos={"logo": None, "firma": None, "tarjeta": None})
        self.assertEqual(_imagenes_pdf(pdf), 0)
        self.assertIn("Coordinaci", _texto_pdf(pdf))

    def test_siempre_cabe_en_una_pagina(self):
        largos = [(f"Estudiante con un nombre larguísimo número {i} " * 3, "11.111.111-1") for i in range(6)]
        pdf = plantilla_oficial.construir_pdf(
            fecha=date(2026, 9, 2), persona_receptora="X", institucion_receptora="Y",
            asignatura="Z", docente="W", estudiantes=largos, borrador=False, recursos=self.recursos,
        )
        self.assertEqual(len(re.findall(rb"/Type /Page\b", pdf)), 1)

    def test_imagen_danada_no_rompe_la_carta(self):
        recursos = dict(self.recursos, firma=b"no soy una imagen")
        with self.assertLogs("cartas.plantilla_oficial", level="WARNING"):
            pdf = _pdf(borrador=False, recursos=recursos)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_carta_final_queda_protegida_contra_cambios(self):
        pdf = _pdf(borrador=False, recursos=self.recursos, proteger=True)
        self.assertIn(b"/Encrypt", pdf)
        self.assertNotIn(b"Santiago, 2 de septiembre", pdf)

    def test_borrador_no_se_protege(self):
        pdf = _pdf(borrador=True, recursos=self.recursos, proteger=True)
        self.assertNotIn(b"/Encrypt", pdf)

    def test_fecha_en_castellano(self):
        self.assertEqual(plantilla_oficial.fecha_carta(date(2026, 12, 25)), "Santiago, 25 de diciembre de 2026")
