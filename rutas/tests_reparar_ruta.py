"""
Render tenía una Ruta de prueba de 4 actividades hecha a mano. El script
liviano la reemplaza por la de 23 sin borrar usuarios ni secciones.
"""
from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from academico.models import Asignatura, Campus, PeriodoAcademico, Sede, Seccion
from rutas.models import RutaActividad, RutaPlantilla, RutaVersion, SeccionRuta
from rutas.services import asignar_ruta_a_seccion, obtener_version_ruta_vigente


class RepararRutaTests(TestCase):
    def setUp(self):
        plantilla = RutaPlantilla.objects.create(nombre="Ruta del Docente A+S", activo=True)
        self.prueba = RutaVersion.objects.create(
            plantilla=plantilla, numero_version=1, estado="BORRADOR", fecha_vigencia_desde=date(2026, 1, 1),
        )
        RutaActividad.objects.bulk_create([
            RutaActividad(ruta_version=self.prueba, orden=1, etapa="DIAGNOSTICO",
                          nombre="Completar curso habilitante en metodología A+S", es_obligatoria=True),
            RutaActividad(ruta_version=self.prueba, orden=2, etapa="DISEÑO",
                          nombre="Diseño de propuesta", es_obligatoria=True),
        ])
        self.prueba.estado = "ACTIVA"
        self.prueba.save()

        sede = Sede.objects.create(nombre="Sede", ciudad="Santiago", activo=True)
        campus = Campus.objects.create(sede=sede, nombre="Campus", direccion="X", activo=True)
        periodo = PeriodoAcademico.objects.create(anio=2026, tipo="SEMESTRE", nombre="P", estado="ACTIVO")
        asignatura = Asignatura.objects.create(codigo="A1", nombre="Asignatura", activo=True)
        self.seccion = Seccion.objects.create(
            periodo=periodo, campus=campus, asignatura=asignatura, nrc="12345", seccion="1",
            jornada="Diurna", horario="L", estado="ACTIVA",
        )
        seccion_ruta = asignar_ruta_a_seccion(self.seccion, self.prueba)
        primera = seccion_ruta.actividades.get(ruta_actividad__orden=1)
        primera.estado = "COMPLETADA"
        primera.fecha_completada = timezone.now()
        primera.save()
        self.usuario = get_user_model().objects.create_user(username="samuel", password="x")

    def test_sin_reparar_solo_avisa(self):
        salida = StringIO()
        call_command("cargar_ruta_docente", stdout=salida)
        self.assertIn("--reparar", salida.getvalue())
        self.assertEqual(obtener_version_ruta_vigente(), self.prueba)

    def test_reparar_crea_las_23_y_mueve_la_seccion(self):
        call_command("cargar_ruta_docente", reparar=True, stdout=StringIO())
        vigente = obtener_version_ruta_vigente()
        self.assertEqual(vigente.numero_version, 2)
        self.assertEqual(vigente.actividades.count(), 23)
        self.prueba.refresh_from_db()
        self.assertEqual(self.prueba.estado, "INACTIVA")

        seccion_ruta = SeccionRuta.objects.get(seccion=self.seccion)
        self.assertEqual(seccion_ruta.ruta_version, vigente)
        self.assertEqual(seccion_ruta.actividades.count(), 23)
        # Lo marcado en una actividad con el mismo número y nombre se conserva.
        self.assertIsNotNone(seccion_ruta.actividades.get(ruta_actividad__orden=1).fecha_completada)
        self.assertTrue(get_user_model().objects.filter(username="samuel").exists())

        # Repetirlo no crea otra versión.
        call_command("cargar_ruta_docente", reparar=True, stdout=StringIO())
        self.assertEqual(RutaVersion.objects.count(), 2)

    def test_ruta_de_prueba_con_otro_nombre(self):
        RutaPlantilla.objects.filter(pk=self.prueba.plantilla_id).update(nombre="Ruta de prueba")
        call_command("cargar_ruta_docente", reparar=True, stdout=StringIO())
        vigente = obtener_version_ruta_vigente()
        self.assertEqual(vigente.actividades.count(), 23)
        self.assertEqual(SeccionRuta.objects.get(seccion=self.seccion).ruta_version, vigente)
