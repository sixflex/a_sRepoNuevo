"""Configuración → Carta oficial: el Coordinador sube su Word y las cartas lo usan."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from reportlab import rl_config

from academico.models import Asignatura, Campus, Docente, PeriodoAcademico, Seccion, Sede
from archivos.services import guardar_archivo
from auditoria.models import AuditoriaCambio
from socios.models import SocioComunitario

from . import plantilla_oficial
from .models import CartaDocumento, CartaEstudiante, PlantillaCarta, SolicitudCarta
from .services import aprobar_y_enviar_carta, generar_borrador_carta
from .tests_firma import _planilla_docx, _texto_pdf

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _recursos_en_uso():
    return plantilla_oficial.recursos_carta(plantilla_oficial.plantilla_activa())


@override_settings(CARTA_PLANTILLA_PATH="", CARTA_FIRMA_PRUEBA_PATH="")
class PlantillaCartaTests(TestCase):
    def setUp(self):
        self.storage = InMemoryStorage()
        parche = patch("archivos.services.obtener_storage_privado", return_value=self.storage)
        parche.start()
        self.addCleanup(parche.stop)
        self.coordinador = get_user_model().objects.create_user(username="coord", password="x")
        self.coordinador.groups.add(Group.objects.get_or_create(name="Coordinador")[0])
        self.client.force_login(self.coordinador)
        self.url = reverse("cartas:plantilla_carta")

    def subir(self, contenido=None, nombre="carta.docx", **extra):
        archivo = SimpleUploadedFile(nombre, contenido if contenido is not None else _planilla_docx(), content_type=DOCX)
        return self.client.post(self.url, {"archivo": archivo, **extra})

    def test_pantalla_sin_carta_explica_que_se_usa(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, "Aún no subes tu carta oficial")
        self.assertContains(respuesta, "Configuración")

    def test_subir_la_deja_en_uso_auditada_y_la_usan_las_cartas(self):
        self.assertRedirects(self.subir(observacion="Firma 2026"), self.url)
        plantilla = PlantillaCarta.objects.get()
        self.assertTrue(plantilla.activa)
        self.assertEqual(plantilla.observacion, "Firma 2026")
        self.assertTrue(AuditoriaCambio.objects.filter(accion="SUBIR_PLANTILLA_CARTA").exists())
        recursos = _recursos_en_uso()
        self.assertEqual(recursos["plantilla"], plantilla)
        self.assertIsNotNone(recursos["firma"])
        self.assertIsNotNone(recursos["tarjeta"])

    def test_subir_otra_reemplaza_y_conserva_el_historial(self):
        self.subir()
        self.subir(_planilla_docx(imagenes_cuerpo=1))
        self.assertEqual(PlantillaCarta.objects.count(), 2)
        self.assertEqual(PlantillaCarta.objects.filter(activa=True).count(), 1)
        self.assertIsNone(_recursos_en_uso()["tarjeta"])

    def test_volver_a_usar_una_anterior(self):
        self.subir()
        primera = PlantillaCarta.objects.get()
        self.subir()
        self.client.post(reverse("cartas:activar_plantilla_carta", args=[primera.pk]))
        primera.refresh_from_db()
        self.assertTrue(primera.activa)
        self.assertEqual(PlantillaCarta.objects.filter(activa=True).count(), 1)

    def test_dejar_de_usar_vuelve_al_respaldo(self):
        self.subir()
        self.client.post(reverse("cartas:desactivar_plantilla_carta"))
        self.assertFalse(PlantillaCarta.objects.filter(activa=True).exists())
        self.assertIsNone(_recursos_en_uso()["plantilla"])

    def test_rechaza_lo_que_no_es_un_word_con_firma(self):
        self.assertContains(self.subir(b"%PDF-1.4", nombre="carta.pdf"), ".docx")
        self.assertContains(self.subir(b"no soy un zip"), "No se pudo abrir")
        self.assertContains(self.subir(_planilla_docx(imagenes_cuerpo=0)), "No encontramos la firma")
        self.assertFalse(PlantillaCarta.objects.exists())

    def test_carta_de_ejemplo_y_descarga(self):
        self.subir()
        plantilla = PlantillaCarta.objects.get()
        ejemplo = self.client.get(reverse("cartas:ejemplo_plantilla_carta", args=[plantilla.pk]))
        self.assertEqual(ejemplo["Content-Type"], "application/pdf")
        self.assertTrue(ejemplo.content.startswith(b"%PDF"))
        descarga = self.client.get(reverse("cartas:descargar_plantilla_carta", args=[plantilla.pk]))
        self.assertEqual(b"".join(descarga.streaming_content), _planilla_docx())

    def test_solo_coordinacion(self):
        docente = get_user_model().objects.create_user(username="doc", password="x")
        docente.groups.add(Group.objects.get_or_create(name="Docente")[0])
        self.client.force_login(docente)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_plantilla_ilegible_avisa_en_vez_de_usar_otra_firma(self):
        self.subir()
        plantilla = PlantillaCarta.objects.get()
        self.storage.delete(plantilla.archivo.storage_key)
        plantilla_oficial._IMAGENES_POR_HASH.clear()
        with self.assertRaises(plantilla_oficial.CartaOficialIlegible):
            plantilla_oficial.recursos_carta(plantilla)
        # El borrador no lleva firma: sigue con el respaldo y queda en el log.
        with self.assertLogs("cartas.plantilla_oficial", level="WARNING"):
            recursos = plantilla_oficial.recursos_carta(plantilla, final=False)
        self.assertIsNone(recursos["plantilla"])
        self.assertIsNotNone(recursos["logo"])
        ejemplo = self.client.get(reverse("cartas:ejemplo_plantilla_carta", args=[plantilla.pk]))
        self.assertEqual(ejemplo.status_code, 404)


@override_settings(CARTA_PLANTILLA_PATH="", CARTA_FIRMA_PRUEBA_PATH="")
class GenerarCartaTests(TestCase):
    """generar_pdf_carta con datos reales: toma la carta oficial activa de la BD."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Sin compresión, el texto del borrador se puede buscar en el PDF.
        cls._compresion = rl_config.pageCompression
        rl_config.pageCompression = 0

    @classmethod
    def tearDownClass(cls):
        rl_config.pageCompression = cls._compresion
        super().tearDownClass()

    def setUp(self):
        self.storage = InMemoryStorage()
        parche = patch("archivos.services.obtener_storage_privado", return_value=self.storage)
        parche.start()
        self.addCleanup(parche.stop)
        plantilla_oficial._IMAGENES_POR_HASH.clear()
        self.usuario = get_user_model().objects.create_user(username="coord", password="x")
        sede = Sede.objects.create(nombre="Santiago", activo=True)
        campus = Campus.objects.create(nombre="Campus Central", sede=sede, activo=True)
        seccion = Seccion.objects.create(
            nrc="12345", seccion="1", estado="ACTIVA", campus=campus,
            asignatura=Asignatura.objects.create(nombre="Taller de Servicio", codigo="TAS101", activo=True),
            periodo=PeriodoAcademico.objects.create(nombre="2026-10", anio=2026),
        )
        socio = SocioComunitario.objects.create(
            nombre_organizacion="Junta de Vecinos", rut="12345678-9", estado_revision="APROBADO",
            es_provisional=False, activo=True, fecha_creacion=timezone.now(),
        )
        docente = Docente.objects.create(
            rut="11111111-1", nombres="Ana", apellidos="Pérez",
            correo_institucional="docente@test.cl", activo=True,
        )
        self.solicitud = SolicitudCarta.objects.create(
            socio=socio, seccion=seccion, campus=campus, sede=sede,
            solicitante_usuario=self.usuario, docente_derivador=docente,
            solicitante_tipo="DOCENTE", solicitante_nombre="Ana Pérez",
            solicitante_correo="docente@test.cl", estado="PENDIENTE",
            persona_receptora="María Soto", institucion_receptora="Junta de Vecinos",
            fecha_solicitud=timezone.now(),
        )
        CartaEstudiante.objects.create(solicitud=self.solicitud, nombre="Luis Rojas", rut="11111111-1", orden=1)

    def subir_plantilla(self):
        archivo = guardar_archivo(
            SimpleUploadedFile("carta.docx", _planilla_docx(), content_type=DOCX), autor=self.usuario,
        )
        return PlantillaCarta.objects.create(archivo=archivo, cargada_por_usuario=self.usuario, activa=True)

    def pdf(self, documento):
        with self.storage.open(documento.archivo.storage_key, "rb") as contenido:
            return contenido.read()

    def test_carta_final_sale_con_la_carta_oficial_activa(self):
        plantilla = self.subir_plantilla()
        solicitud, _ = aprobar_y_enviar_carta(self.solicitud.pk, self.usuario)
        documento = solicitud.documentos.get()
        self.assertEqual(documento.tipo, "PDF")
        self.assertEqual(documento.plantilla, plantilla)
        self.assertIn(b"/Encrypt", self.pdf(documento))  # final protegida

    def test_borrador_sale_marcado_y_sin_carta_oficial(self):
        _, documento = generar_borrador_carta(self.solicitud.pk, self.usuario)
        self.assertEqual(documento.tipo, "BORRADOR")
        self.assertIsNone(documento.plantilla)
        self.assertIn("BORRADOR", _texto_pdf(self.pdf(documento)))

    def test_carta_final_no_se_emite_si_la_oficial_no_se_puede_leer(self):
        plantilla = self.subir_plantilla()
        self.storage.delete(plantilla.archivo.storage_key)
        with self.assertRaises(plantilla_oficial.CartaOficialIlegible):
            aprobar_y_enviar_carta(self.solicitud.pk, self.usuario)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "PENDIENTE")  # la aprobación se deshace
        self.assertFalse(CartaDocumento.objects.exists())

    def test_borrador_sigue_aunque_la_oficial_no_se_pueda_leer(self):
        plantilla = self.subir_plantilla()
        self.storage.delete(plantilla.archivo.storage_key)
        with self.assertLogs("cartas.plantilla_oficial", level="WARNING"):
            _, documento = generar_borrador_carta(self.solicitud.pk, self.usuario)
        self.assertIsNone(documento.plantilla)
