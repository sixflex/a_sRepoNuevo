"""Configuración → Carta oficial: el Coordinador sube su Word y las cartas lo usan."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from auditoria.models import AuditoriaCambio

from . import plantilla_oficial
from .models import PlantillaCarta
from .tests_firma import _planilla_docx

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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
        recursos = plantilla_oficial.recursos_carta()
        self.assertEqual(recursos["plantilla"], plantilla)
        self.assertIsNotNone(recursos["firma"])
        self.assertIsNotNone(recursos["tarjeta"])

    def test_subir_otra_reemplaza_y_conserva_el_historial(self):
        self.subir()
        self.subir(_planilla_docx(imagenes_cuerpo=1))
        self.assertEqual(PlantillaCarta.objects.count(), 2)
        self.assertEqual(PlantillaCarta.objects.filter(activa=True).count(), 1)
        self.assertIsNone(plantilla_oficial.recursos_carta()["tarjeta"])

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
        self.assertIsNone(plantilla_oficial.recursos_carta()["plantilla"])

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

    def test_plantilla_ilegible_no_rompe_las_cartas(self):
        self.subir()
        self.storage.delete(PlantillaCarta.objects.get().archivo.storage_key)
        plantilla_oficial._imagenes_archivo_cacheadas.cache_clear()
        with self.assertLogs("cartas.plantilla_oficial", level="WARNING"):
            recursos = plantilla_oficial.recursos_carta()
        self.assertIsNone(recursos["plantilla"])
        self.assertIsNotNone(recursos["logo"])
