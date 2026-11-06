from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from core.models import Noticia
from archivos.models import RecursoRepositorio
from archivos.forms import NoticiaForm


class TestSP8T02NoticiasYRecursos(TestCase):
    def setUp(self):
        self.client = Client()

    def test_criterio_1_noticias_no_se_duplican_por_url(self):
        """
        Criterio de aceptación 1: Las noticias no se duplican por URL.
        Valida que NoticiaForm rechaza una nueva noticia si ya existe registrada la misma url_fuente.
        """
        Noticia.objects.create(
            titulo="Noticia Existente UA",
            fuente="Diario UA",
            url_fuente="https://www.uautonoma.cl/noticias/lanzamiento-as",
            fecha_publicacion=timezone.now(),
            estado="PUBLICADA"
        )

        data_duplicada = {
            "titulo": "Intento de Noticia Duplicada",
            "fuente": "Prensa Externa",
            "url_fuente": "https://www.uautonoma.cl/noticias/lanzamiento-as",
            "fecha_publicacion": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "estado": "PUBLICADA"
        }

        form = NoticiaForm(data=data_duplicada)
        self.assertFalse(form.is_valid())
        self.assertIn("url_fuente", form.errors)
        self.assertEqual(
            form.errors["url_fuente"][0],
            "Ya existe una noticia registrada con esta misma URL de fuente."
        )

    def test_criterio_2_recurso_privado_no_aparece_en_repositorio_publico(self):
        """
        Criterio de aceptación 2: Un recurso privado no aparece ni se descarga desde el portal público.
        Valida que la vista pública del repositorio sólo incluya los recursos con visibilidad PUBLICO.
        """
        RecursoRepositorio.objects.create(
            titulo="Reglamento Interno Confidencial",
            categoria="Reglamentos",
            visibilidad="PRIVADO",
            estado="PUBLICADO"
        )
        RecursoRepositorio.objects.create(
            titulo="Guía Pública Metodológica A+S",
            categoria="Guías metodológicas",
            visibilidad="PUBLICO",
            estado="PUBLICADO"
        )

        url = reverse("archivos:repositorio_publico")
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Guía Pública Metodológica A+S")
        self.assertNotContains(response, "Reglamento Interno Confidencial")