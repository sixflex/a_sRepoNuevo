from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from academico.models import Seccion
from core import indicadores
from encuestas import services as encuestas_services
from encuestas.models import RespuestaFormulario
from planificacion.models import Planificacion
from proyectos.models import Equipo, IntegranteEquipo
from rutas.models import SeccionRuta
from socios.models import ParticipacionSocio, PostulacionSocio, SocioComunitario


class CargarDatosDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        salida = StringIO()
        call_command("cargar_formularios", stdout=salida)
        call_command("cargar_ruta_docente", stdout=salida)
        call_command("cargar_datos_demo", stdout=salida)

    def test_crea_secciones_desde_las_planificaciones(self):
        self.assertEqual(Seccion.objects.count(), 15)
        self.assertEqual(Planificacion.objects.filter(filas_observadas__gt=0).count(), 3)
        self.assertEqual(SeccionRuta.objects.filter(estado="COMPLETADA").count(), 2)

    def test_equipos_con_socio_vigente(self):
        self.assertEqual(Equipo.objects.count(), 70)
        self.assertEqual(IntegranteEquipo.objects.count(), 350)
        con_socio = Equipo.objects.filter(participaciones_socios__fecha_fin__isnull=True).distinct()
        self.assertEqual(con_socio.count(), 70)

    def test_historico_sin_secciones_y_postulaciones(self):
        historicas = ParticipacionSocio.objects.filter(origen="HISTORICO")
        self.assertTrue(historicas.exists())
        self.assertFalse(historicas.filter(seccion__isnull=False).exists())
        self.assertEqual(PostulacionSocio.objects.count(), 8)

    def test_panel_muestra_satisfaccion(self):
        self.assertTrue(RespuestaFormulario.objects.filter(seccion__isnull=False).exists())
        self.assertTrue(indicadores.satisfaccion({})["hay_datos"])

    def test_no_carga_dos_veces(self):
        with self.assertRaises(CommandError):
            call_command("cargar_datos_demo", stdout=StringIO())

    def test_postulaciones_muestran_la_ficha_antes_de_decidir(self):
        coordinador = get_user_model().objects.filter(groups__name="Coordinador").first()
        self.client.force_login(coordinador)
        postulacion = PostulacionSocio.objects.filter(estado="RECIBIDA").select_related("respuesta_formulario").first()
        detalle = reverse("socios:detalle_postulacion", args=[postulacion.id])
        self.assertContains(self.client.get(reverse("socios:lista_postulaciones")), detalle)

        respuesta = self.client.get(detalle)
        pregunta, texto = encuestas_services.resumen_respuesta(postulacion.respuesta_formulario)[0]
        self.assertContains(respuesta, pregunta.bloque.titulo)
        self.assertContains(respuesta, texto)
        self.assertContains(respuesta, reverse("socios:revisar_postulacion", args=[postulacion.id]))

        # Si falta el motivo de rechazo, vuelve a la misma página con el aviso.
        error = self.client.post(
            reverse("socios:revisar_postulacion", args=[postulacion.id]), {"estado": "RECHAZADA"},
        )
        self.assertRedirects(error, detalle)

    def test_mapa_publico_sin_datos_personales(self):
        publico = indicadores.mapa(indicadores.filtros_publicos({}))
        self.assertTrue(publico["puntos"])
        self.assertNotIn("detalle", publico["puntos"][0])
        respuesta = self.client.get(reverse("core:inicio"))
        socio = SocioComunitario.objects.exclude(direccion_exacta=None).first()
        self.assertContains(respuesta, 'id="mapa-puntos"')
        self.assertNotContains(respuesta, socio.direccion_exacta)

    def test_mapa_del_coordinador_trae_direccion_y_contacto(self):
        privado = indicadores.mapa(indicadores.filtros_publicos({}), detalle=True)
        socios = [socio for punto in privado["puntos"] for socio in punto["detalle"]]
        self.assertEqual(len(socios), privado["total_socios"])
        self.assertTrue(any(socio["direccion"] and socio["contacto"] for socio in socios))
        self.assertNotIn("intervenciones", socios[0])
