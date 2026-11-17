"""El "Volver" de la Ruta del Docente lleva a la página desde donde la abrió."""

from django.test import RequestFactory, SimpleTestCase
from django.contrib.sessions.backends.signed_cookies import SessionStore

from rutas import views


class VolverRutaDocenteTests(SimpleTestCase):
    def _volver(self, sesion, **get):
        request = RequestFactory().get("/", get)
        request.session = sesion
        ruta = type("SeccionRuta", (), {"pk": 7, "seccion_id": 3})()
        return views._volver_ruta_docente(request, ruta)

    def test_desde_inicio_vuelve_al_inicio_aunque_despues_se_recargue(self):
        sesion = SessionStore()
        self.assertEqual(self._volver(sesion, desde="inicio")[1], "Volver al inicio")
        # Marcar una actividad vuelve a la Ruta sin el parámetro: se recuerda.
        url, texto = self._volver(sesion)
        self.assertEqual(texto, "Volver al inicio")
        self.assertEqual(url, views.reverse("core:inicio_docente"))

    def test_desde_la_seccion_o_sin_origen_vuelve_a_la_seccion(self):
        sesion = SessionStore()
        self.assertEqual(self._volver(sesion)[1], "Volver a la sección")
        self._volver(sesion, desde="inicio")
        self.assertEqual(self._volver(sesion, desde="seccion")[1], "Volver a la sección")

    def test_valor_desconocido_no_se_usa(self):
        sesion = SessionStore()
        self.assertEqual(self._volver(sesion, desde="https://otro.sitio")[1], "Volver a la sección")
