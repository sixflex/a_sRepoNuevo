from datetime import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Noticia
from .noticias import NoticiaNoLeida, leer_noticia

HTML_UA = """<html><head>
<title>Estudiantes A+S apoyan a emprendedores - Universidad Autónoma de Chile</title>
<meta property="og:title" content="Estudiantes A+S apoyan a emprendedores">
<meta property="og:description" content="Un proyecto de Aprendizaje + Servicio en Talca.">
<meta property="og:image" content="https://www.uautonoma.cl/foto.jpg">
<meta property="article:published_time" content="2026-10-20T10:00:00+00:00">
</head><body></body></html>"""


class LeerNoticiaTests(TestCase):
    def test_lee_titulo_resumen_imagen_y_fecha(self):
        with mock.patch("publico.noticias._descargar", return_value=HTML_UA):
            datos = leer_noticia("https://www.uautonoma.cl/noticias/a-s/#top")
        self.assertEqual(datos["url_fuente"], "https://www.uautonoma.cl/noticias/a-s")
        self.assertEqual(datos["titulo"], "Estudiantes A+S apoyan a emprendedores")
        self.assertEqual(datos["imagen_url"], "https://www.uautonoma.cl/foto.jpg")
        self.assertEqual(datos["fecha_publicacion"].date().isoformat(), "2026-10-20")

    def test_no_visita_sitios_que_no_son_de_la_universidad(self):
        with mock.patch("publico.noticias._descargar") as descargar:
            with self.assertRaises(NoticiaNoLeida):
                leer_noticia("https://ejemplo.com/noticia")
            with self.assertRaises(NoticiaNoLeida):
                leer_noticia("https://uautonoma.cl.ejemplo.com/noticia")
        descargar.assert_not_called()

    def test_sitio_caido(self):
        with mock.patch("publico.noticias._descargar", side_effect=TimeoutError):
            with self.assertRaises(NoticiaNoLeida):
                leer_noticia("https://www.uautonoma.cl/noticias/x")


class PestanaNoticiasTests(TestCase):
    def setUp(self):
        usuario = get_user_model().objects.create_user("coord", password="x")
        usuario.groups.add(Group.objects.get_or_create(name="Coordinador")[0])
        self.client.force_login(usuario)
        self.url = reverse("publico:noticias")

    def publicar(self, **cambios):
        datos = {
            "url_fuente": "https://www.uautonoma.cl/noticias/a-s",
            "titulo": "Noticia A+S", "resumen": "Resumen", "imagen_url": "",
            "fecha_publicacion": "2026-10-20", "fuente": "Universidad Autónoma de Chile", "leida": "1",
        }
        datos.update(cambios)
        return self.client.post(self.url, datos)

    def test_pegar_enlace_precarga_el_formulario(self):
        with mock.patch("publico.noticias._descargar", return_value=HTML_UA):
            respuesta = self.client.post(self.url, {"accion": "leer", "url": "https://www.uautonoma.cl/noticias/a-s"})
        self.assertContains(respuesta, "Revisa los datos y publica")
        self.assertEqual(respuesta.context["form"].initial["titulo"], "Estudiantes A+S apoyan a emprendedores")

    def test_si_no_se_puede_leer_se_completa_a_mano(self):
        respuesta = self.client.post(self.url, {"accion": "leer", "url": "https://ejemplo.com/n"})
        self.assertContains(respuesta, "Completa los datos")
        self.assertEqual(respuesta.context["form"].initial["url_fuente"], "https://ejemplo.com/n")

    def test_publica_y_aparece_en_el_portal(self):
        self.assertRedirects(self.publicar(), self.url)
        noticia = Noticia.objects.get()
        self.assertEqual(noticia.estado, "PUBLICADA")
        self.assertIsNotNone(noticia.fecha_sincronizacion)
        self.client.logout()
        self.assertContains(self.client.get(reverse("core:inicio")), "Noticia A+S")

    def test_no_se_repite_la_url(self):
        self.publicar()
        respuesta = self.publicar(url_fuente="https://www.uautonoma.cl/noticias/a-s/")
        self.assertContains(respuesta, "Esta noticia ya está agregada.")
        self.assertEqual(Noticia.objects.count(), 1)

    def test_ocultar_la_saca_del_portal(self):
        self.publicar()
        noticia = Noticia.objects.get()
        self.client.post(reverse("publico:cambiar_estado_noticia", args=[noticia.pk]))
        noticia.refresh_from_db()
        self.assertEqual(noticia.estado, "OCULTA")
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("core:inicio")), "Noticia A+S")

    def test_eliminar(self):
        self.publicar()
        self.client.post(reverse("publico:eliminar_noticia", args=[Noticia.objects.get().pk]))
        self.assertFalse(Noticia.objects.exists())

    def test_solo_coordinacion(self):
        self.client.logout()
        self.assertNotEqual(self.client.get(self.url).status_code, 200)
