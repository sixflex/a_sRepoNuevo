"""
Ficha única del proyecto A+S (reunión con el cliente 10-11-2026):
formularios precargados, Ruta paso a paso, registro de reflexión, vista
simple del Coordinador con ZIP + ficha PDF, encuesta masiva a socios y
enlace del portal a la convocatoria de los centros de negocio.
"""

import io
import zipfile
from types import SimpleNamespace

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from encuestas import precarga
from encuestas import services as encuestas_services
from encuestas.definiciones import evaluaciones, ficha_emprendedores, registro_reflexion
from encuestas.definiciones.formulario_proyecto_as import DEFINICION as FORMULARIO_PROYECTO
from encuestas.models import EnlaceFormulario
from encuestas.semillas import crear_formulario

from .models import RutaActividad, SeccionActividad
from .paso_a_paso import armar_etapas
from . import tests as rutas_tests


def publicar(definicion):
    version = crear_formulario(definicion)
    encuestas_services.publicar(version)
    version.refresh_from_db()
    return version


class FichaUnicaBase(TestCase):
    def setUp(self):
        rutas_tests.SeguimientoRutaTestCase.setUp(self)
        from socios.models import ContactoSocio, ParticipacionSocio, SocioComunitario
        from proyectos.models import Equipo

        self.socio = SocioComunitario.objects.create(
            nombre_organizacion="Junta de Vecinos",
            estado_revision="APROBADO",
            es_provisional=False,
            activo=True,
            fecha_creacion=timezone.now(),
        )
        ContactoSocio.objects.create(
            socio=self.socio, nombre="Contacto", correo="socio@example.com",
            es_principal=True, activo=True,
        )

        equipo = Equipo.objects.create(
            seccion=self.seccion, numero_grupo=1, informante_nombre="Estudiante",
            informante_correo="estudiante@cloud.uautonoma.cl", estado="Registrado",
        )
        ParticipacionSocio.objects.create(socio=self.socio, seccion=self.seccion, equipo=equipo, origen="OPERATIVO")

    def agregar_actividad(self, orden, nombre, etapa="Etapa de prueba"):
        version = self.ruta.ruta_version
        version.estado = "BORRADOR"
        version.save(update_fields=["estado"])
        ruta_actividad = RutaActividad.objects.create(
            ruta_version=version, etapa=etapa, nombre=nombre, es_obligatoria=True, orden=orden,
        )
        version.estado = "ACTIVA"
        version.save(update_fields=["estado"])
        return SeccionActividad.objects.create(
            seccion_ruta=self.ruta, ruta_actividad=ruta_actividad, estado="PENDIENTE",
        )


class PrecargaTests(FichaUnicaBase):
    def test_formulario_del_proyecto_viene_con_datos_de_la_seccion(self):
        version = publicar(FORMULARIO_PROYECTO)
        enlace = encuestas_services.crear_enlace(version, seccion=self.seccion)

        self.client.force_login(self.usuario_docente)
        respuesta = self.client.get(reverse("encuestas:responder", args=[enlace.token]))

        self.assertContains(respuesta, 'value="Asignatura HU-02"')
        self.assertContains(respuesta, f'value="{self.docente.nombres} {self.docente.apellidos}"')
        self.assertContains(respuesta, "Desde la sección")
        self.assertContains(respuesta, "Algunas respuestas ya vienen llenas")

    def test_enlace_sin_seccion_no_precarga_nada(self):
        version = publicar(FORMULARIO_PROYECTO)
        enlace = encuestas_services.crear_enlace(version)

        respuesta = self.client.get(reverse("encuestas:responder", args=[enlace.token]))

        self.assertNotContains(respuesta, 'value="Asignatura HU-02"')
        self.assertNotContains(respuesta, "Algunas respuestas ya vienen llenas")

    def test_reflexion_elige_el_momento_pendiente_de_la_ruta(self):
        primera = self.agregar_actividad(12, "Primera reflexión")
        self.agregar_actividad(15, "Segunda reflexión")
        version = publicar(registro_reflexion.DEFINICION)
        _, preguntas = encuestas_services.cargar_estructura(version)

        inicial, _ = precarga.precargar(version, preguntas, self.seccion, self.usuario_docente)
        self.assertIn(registro_reflexion.ANTES, inicial.values())

        primera.completada_por_docente = self.docente
        primera.save()
        inicial, _ = precarga.precargar(version, preguntas, self.seccion, self.usuario_docente)
        self.assertIn(registro_reflexion.DURANTE, inicial.values())


class RutaPasoAPasoTests(FichaUnicaBase):
    def test_etapa_actual_es_la_primera_con_obligatorias_pendientes(self):
        def actividad(etapa, hecha):
            return SimpleNamespace(
                ruta_actividad=SimpleNamespace(etapa=etapa, es_obligatoria=True),
                completada_por_docente_id=1 if hecha else None,
                evidencias=SimpleNamespace(all=lambda: []),
            )

        etapas, actual = armar_etapas([actividad("Inicio", True), actividad("Diseño", False), actividad("Cierre", False)])

        self.assertEqual(actual["nombre"], "Diseño")
        self.assertTrue(etapas[0]["completa"])
        self.assertEqual(actual["numero"], 2)

    def test_reflexion_tiene_su_boton_y_el_formulario_por_seccion(self):
        self.agregar_actividad(12, "Realizar primera actividad de reflexión")
        publicar(registro_reflexion.DEFINICION)

        self.client.force_login(self.usuario_docente)
        respuesta = self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))

        self.assertContains(respuesta, "Registrar reflexión")
        self.assertContains(respuesta, "Ver dinámicas sugeridas")
        enlace = EnlaceFormulario.objects.get(version__plantilla__codigo=registro_reflexion.CODIGO, seccion=self.seccion)
        self.assertContains(respuesta, reverse("encuestas:responder", args=[enlace.token]))

    def test_nada_se_bloquea_todas_las_etapas_se_pueden_abrir(self):
        self.agregar_actividad(20, "Completar evaluación", etapa="Cierre y reporte")

        self.client.force_login(self.usuario_docente)
        respuesta = self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))

        self.assertContains(respuesta, "Próximas etapas")
        self.assertContains(respuesta, "Completar evaluación")
        self.assertContains(respuesta, "Marcar como hecha")


class CoordinadorFichaTests(FichaUnicaBase):
    def completar_ruta(self):
        self.ruta.estado = "COMPLETADA"
        self.ruta.save(update_fields=["estado"])

    def test_zip_trae_la_ficha_cuando_la_ruta_esta_completada(self):
        self.completar_ruta()
        self.client.force_login(self.usuario_coordinador)
        respuesta = self.client.get(reverse("rutas:descargar_expediente", args=[self.ruta.id]))

        self.assertEqual(respuesta.status_code, 200)
        contenido = zipfile.ZipFile(io.BytesIO(b"".join(respuesta.streaming_content)))
        self.assertEqual(contenido.namelist(), ["Ficha del proyecto.pdf"])
        self.assertTrue(contenido.read("Ficha del proyecto.pdf").startswith(b"%PDF"))

    def test_zip_sin_ficha_mientras_la_ruta_sigue_abierta(self):
        self.client.force_login(self.usuario_coordinador)
        respuesta = self.client.get(reverse("rutas:descargar_expediente", args=[self.ruta.id]))

        self.assertEqual(respuesta.status_code, 200)
        contenido = zipfile.ZipFile(io.BytesIO(b"".join(respuesta.streaming_content)))
        self.assertNotIn("Ficha del proyecto.pdf", contenido.namelist())

    def test_ficha_en_el_navegador_solo_con_la_ruta_completada(self):
        url = reverse("rutas:ver_ficha_coordinacion", args=[self.ruta.id])
        self.client.force_login(self.usuario_coordinador)

        self.assertEqual(self.client.get(url).status_code, 403)
        detalle = self.client.get(reverse("rutas:detalle_ruta_coordinacion", args=[self.ruta.id]))
        self.assertContains(detalle, "Disponible cuando el docente complete la Ruta")
        self.assertNotContains(detalle, url)

        excel_url = reverse("rutas:exportar_ficha_excel", args=[self.ruta.id])
        self.assertEqual(self.client.get(excel_url).status_code, 403)

        self.completar_ruta()
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ficha del proyecto")
        self.assertContains(respuesta, "Exportar a Excel")
        self.assertContains(self.client.get(reverse("rutas:detalle_ruta_coordinacion", args=[self.ruta.id])), url)

    def test_ficha_se_exporta_a_excel_con_preguntas_y_respuestas(self):
        from openpyxl import load_workbook

        self.completar_ruta()
        self.client.force_login(self.usuario_coordinador)
        respuesta = self.client.get(reverse("rutas:exportar_ficha_excel", args=[self.ruta.id]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(".xlsx", respuesta["Content-Disposition"])
        libro = load_workbook(io.BytesIO(respuesta.content))
        self.assertEqual(libro.sheetnames, ["Ficha", "Formularios", "Grupos", "Avance por etapa", "Evidencias"])
        encabezado = [c.value for c in libro["Formularios"][1]]
        self.assertEqual(encabezado, ["Formulario", "Grupo", "Fecha", "Pregunta", "Respuesta"])
        valores = [c.value for fila in libro["Ficha"].iter_rows() for c in fila]
        self.assertIn(self.seccion.nrc, valores)

    def test_el_docente_no_abre_la_ficha_del_coordinador(self):
        self.completar_ruta()
        self.client.force_login(self.usuario_docente)
        respuesta = self.client.get(reverse("rutas:ver_ficha_coordinacion", args=[self.ruta.id]))
        self.assertEqual(respuesta.status_code, 403)

    def test_vista_simple_muestra_en_que_etapa_va(self):
        self.client.force_login(self.usuario_coordinador)
        respuesta = self.client.get(reverse("rutas:detalle_ruta_coordinacion", args=[self.ruta.id]))

        self.assertContains(respuesta, "Va en <strong>Etapa de prueba</strong>", html=False)
        self.assertContains(respuesta, "Descargar evidencias (ZIP)")


class EncuestaSociosTests(FichaUnicaBase):
    def setUp(self):
        super().setUp()
        self.version = publicar(evaluaciones.SOCIOS_COMUNITARIOS)
        self.url = reverse("rutas:encuesta_socios")

    def test_solo_el_coordinador(self):
        self.client.force_login(self.usuario_docente)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_envia_un_enlace_propio_a_cada_socio_y_no_repite(self):
        self.client.force_login(self.usuario_coordinador)
        periodo = self.seccion.periodo.pk

        self.client.post(self.url, {"periodo": periodo})
        enlace = EnlaceFormulario.objects.get(socio=self.socio)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(str(enlace.token), mail.outbox[0].body)

        self.client.post(self.url, {"periodo": periodo})
        self.assertEqual(len(mail.outbox), 1)

        self.client.post(self.url, {"periodo": periodo, "reenviar": "1"})
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(EnlaceFormulario.objects.filter(socio=self.socio).count(), 1)

    def test_qr_del_docente_ya_no_incluye_la_encuesta_de_socios(self):
        publicar(evaluaciones.ESTUDIANTES)
        url = reverse("rutas:formularios_qr") + "?proceso=EVALUACION_AS"

        self.client.force_login(self.usuario_docente)
        titulos = [f["titulo"] for f in self.client.get(url).context["formularios"]]
        self.assertNotIn(evaluaciones.SOCIOS_COMUNITARIOS["titulo"], titulos)
        self.assertIn(evaluaciones.ESTUDIANTES["titulo"], titulos)

        self.client.force_login(self.usuario_coordinador)
        titulos = [f["titulo"] for f in self.client.get(url).context["formularios"]]
        self.assertIn(evaluaciones.SOCIOS_COMUNITARIOS["titulo"], titulos)


class PortalConvocatoriaTests(TestCase):
    def test_portal_enlaza_la_ficha_de_los_centros_de_negocio(self):
        self.assertNotContains(self.client.get(reverse("core:inicio")), "Convocatoria a los centros de negocio")

        version = publicar(ficha_emprendedores.DEFINICION)
        enlace = EnlaceFormulario.objects.filter(version=version, seccion__isnull=True).first()

        respuesta = self.client.get(reverse("core:inicio"))
        self.assertContains(respuesta, "Convocatoria a los centros de negocio")
        self.assertContains(respuesta, reverse("encuestas:responder", args=[enlace.token]))


class PromedioPorDocenteTests(TestCase):
    """Promedio de todas las Rutas de un docente (reunión con el cliente, 2026-11)."""

    def test_promedio_simple_de_las_rutas(self):
        from types import SimpleNamespace

        from .services import promedio_rutas

        rutas = [
            SimpleNamespace(completadas_obligatorias=10, total_obligatorias=20),
            SimpleNamespace(completadas_obligatorias=20, total_obligatorias=20),
            SimpleNamespace(completadas_obligatorias=0, total_obligatorias=0),
        ]
        self.assertEqual(promedio_rutas(rutas), 50)
        self.assertIsNone(promedio_rutas([]))
