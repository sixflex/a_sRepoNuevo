from django.test import TestCase

from academico.models import (Asignatura,Campus,Carrera,Facultad,PeriodoAcademico,Seccion,SeccionCarrera,Sede)
from rutas.models import (RutaActividad,RutaPlantilla,RutaVersion,SeccionActividad,SeccionRuta,)
from rutas.services import asignar_ruta_as_si_corresponde

class RutaDocenteTestCase(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre="Sede Santiago",activo=True,)

        self.campus = Campus.objects.create(sede=self.sede,nombre="Campus Providencia",activo=True,)

        self.facultad = Facultad.objects.create(nombre="Facultad de Ingeniería",activo=True,)

        self.carrera = Carrera.objects.create(facultad=self.facultad,nombre="Ingeniería Civil Informática",activo=True,)

        self.asignatura = Asignatura.objects.create(codigo="AS001",nombre="Asignatura A+S",activo=True,)

        self.asignatura.carreras.add(self.carrera)

        self.periodo = PeriodoAcademico.objects.create(anio=2026,tipo="Segundo semestre",nombre="Primavera 2026",estado="Activo",)

        self.plantilla = RutaPlantilla.objects.create(nombre="Ruta del Docente A+S",descripcion="Ruta 2026",activo=True,)

        self.version = RutaVersion.objects.create(plantilla=self.plantilla,numero_version=1,estado="ACTIVA",)

        for orden in range(1, 24):
            RutaActividad.objects.create(ruta_version=self.version,etapa="Etapa de prueba",nombre=f"Actividad {orden}",es_obligatoria=True,orden=orden,)

    def crear_seccion(self, nrc, declaracion_as=True):
        seccion = Seccion.objects.create(
            periodo=self.periodo,
            campus=self.campus,
            asignatura=self.asignatura,
            nrc=nrc,
            seccion="1",
            estado="Activo",
        )

        SeccionCarrera.objects.create(
            seccion=seccion,
            carrera=self.carrera,
            declaracion_as=declaracion_as,
        )

        return seccion

    def test_seccion_as_recibe_ruta(self):
        seccion = self.crear_seccion("RUTA001")

        ruta = asignar_ruta_as_si_corresponde(seccion)

        self.assertIsNotNone(ruta)
        self.assertEqual(ruta.seccion, seccion)
        self.assertEqual(ruta.ruta_version, self.version)
        self.assertEqual(ruta.estado, "EN_PROGRESO")
        self.assertEqual(ruta.porcentaje_final, 0)

    def test_seccion_as_recibe_23_actividades(self):
        seccion = self.crear_seccion("RUTA002")

        ruta = asignar_ruta_as_si_corresponde(seccion)

        total = SeccionActividad.objects.filter(seccion_ruta=ruta).count()

        self.assertEqual(total, 23)

    def test_reasignar_ruta_no_duplica_actividades(self):
        seccion = self.crear_seccion("RUTA003")

        asignar_ruta_as_si_corresponde(seccion)
        asignar_ruta_as_si_corresponde(seccion)

        ruta = SeccionRuta.objects.get(seccion=seccion)

        total = SeccionActividad.objects.filter(seccion_ruta=ruta).count()

        self.assertEqual(total, 23)
        self.assertEqual(SeccionRuta.objects.filter(seccion=seccion).count(),1,)

    def test_seccion_no_as_no_recibe_ruta(self):
        seccion = self.crear_seccion(
            "RUTA004",
            declaracion_as=False,
        )

        resultado = asignar_ruta_as_si_corresponde(seccion)

        self.assertIsNone(resultado)
        self.assertFalse(SeccionRuta.objects.filter(seccion=seccion).exists())

    def test_sin_version_activa_no_asigna_ruta(self):
        self.version.estado = "INACTIVA"
        self.version.save(update_fields=["estado"])

        seccion = self.crear_seccion("RUTA005")

        resultado = asignar_ruta_as_si_corresponde(seccion)

        self.assertIsNone(resultado)
        self.assertFalse(SeccionRuta.objects.filter(seccion=seccion).exists())