from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from auditoria.models import AuditoriaCambio

from .models import RecursoRepositorio


class RepositorioTests(TestCase):
    """Repositorio público (RF-PUB-02): el Coordinador publica, retira y reemplaza."""

    def setUp(self):
        self.storage = InMemoryStorage()
        parche = patch("archivos.services.obtener_storage_privado", return_value=self.storage)
        parche.start()
        self.addCleanup(parche.stop)

        self.coordinador = get_user_model().objects.create_user(username="coord", password="x")
        self.coordinador.groups.add(Group.objects.create(name="Coordinador"))
        self.client.force_login(self.coordinador)

    def subir(self, titulo="Guía A+S", visibilidad="PUBLICO", nombre="guia.pdf", **extra):
        datos = {
            "titulo": titulo, "descripcion": "", "categoria": "Guías metodológicas",
            "visibilidad": visibilidad, "url_externa": "",
        }
        if nombre:
            datos["archivo_subido"] = SimpleUploadedFile(nombre, b"%PDF-1.4 prueba", content_type="application/pdf")
        datos.update(extra)
        return self.client.post(reverse("archivos:crear_recurso"), datos)

    def test_subir_documento_queda_publicado_y_auditado(self):
        response = self.subir()

        self.assertRedirects(response, reverse("archivos:repositorio"))
        recurso = RecursoRepositorio.objects.get()
        self.assertEqual(recurso.estado, "PUBLICADO")
        self.assertEqual(recurso.archivo.nombre_original, "guia.pdf")
        self.assertTrue(AuditoriaCambio.objects.filter(accion="CREAR_RECURSO").exists())

    def test_sin_archivo_ni_enlace_no_se_guarda(self):
        response = self.subir(nombre=None)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(RecursoRepositorio.objects.exists())

    def test_solo_acepta_pdf_word_y_excel(self):
        self.subir(nombre="foto.png")

        self.assertFalse(RecursoRepositorio.objects.exists())

    def test_portal_publico_muestra_solo_publicos_y_publicados(self):
        self.subir("Público")
        self.subir("Privado", visibilidad="PRIVADO")
        self.subir("Retirado")
        retirado = RecursoRepositorio.objects.get(titulo="Retirado")
        self.client.post(reverse("archivos:cambiar_estado_recurso", args=[retirado.pk]))
        self.client.logout()

        response = self.client.get(reverse("archivos:repositorio_publico"))

        self.assertContains(response, "Público")
        self.assertNotContains(response, "Privado")
        self.assertNotContains(response, "Retirado")

    def test_visitante_descarga_publico_pero_no_privado(self):
        self.subir("Público")
        self.subir("Privado", visibilidad="PRIVADO")
        publico = RecursoRepositorio.objects.get(titulo="Público")
        privado = RecursoRepositorio.objects.get(titulo="Privado")
        self.client.logout()

        ok = self.client.get(reverse("archivos:descargar_recurso_publico", args=[publico.pk]))
        no = self.client.get(reverse("archivos:descargar_recurso_publico", args=[privado.pk]))

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(b"".join(ok.streaming_content), b"%PDF-1.4 prueba")
        self.assertEqual(no.status_code, 404)

    def test_reemplazar_archivo_al_editar(self):
        self.subir()
        recurso = RecursoRepositorio.objects.get()

        self.client.post(reverse("archivos:editar_recurso", args=[recurso.pk]), {
            "titulo": "Guía A+S 2026", "descripcion": "", "categoria": "Guías metodológicas",
            "visibilidad": "PUBLICO", "url_externa": "",
            "archivo_subido": SimpleUploadedFile("guia-2026.docx", b"nuevo"),
        })

        recurso.refresh_from_db()
        self.assertEqual(recurso.titulo, "Guía A+S 2026")
        self.assertEqual(recurso.archivo.nombre_original, "guia-2026.docx")

    def test_docente_no_administra_el_repositorio(self):
        docente = get_user_model().objects.create_user(username="doc", password="x")
        docente.groups.add(Group.objects.create(name="Docente"))
        self.client.force_login(docente)

        self.assertEqual(self.client.get(reverse("archivos:repositorio")).status_code, 403)
