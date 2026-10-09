from django.test import TestCase

from academico.models import (Asignatura,Campus,Carrera,Facultad,PeriodoAcademico,Seccion,SeccionCarrera,Sede)
from rutas.models import (RutaActividad,RutaPlantilla,RutaVersion,SeccionActividad,SeccionRuta,)
from rutas.services import asignar_ruta_as_si_corresponde
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from academico.models import Docente, SeccionDocente
from rutas.views import recalcular_avance

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


class SeguimientoRutaTestCase(TestCase):
    def setUp(self):
        Usuario = get_user_model()

        grupo_docente, _ = Group.objects.get_or_create(
            name="Docente"
        )
        grupo_coordinador, _ = Group.objects.get_or_create(
            name="Coordinador"
        )

        self.usuario_docente = Usuario.objects.create_user(
            username="docente_prueba",
            password="Prueba12345"
        )
        self.usuario_docente.groups.add(grupo_docente)

        self.usuario_otro = Usuario.objects.create_user(
            username="docente_otro",
            password="Prueba12345"
        )
        self.usuario_otro.groups.add(grupo_docente)

        self.usuario_coordinador = Usuario.objects.create_user(
            username="coordinador_prueba",
            password="Prueba12345"
        )
        self.usuario_coordinador.groups.add(grupo_coordinador)

        self.docente = Docente.objects.create(
            usuario=self.usuario_docente,
            rut="11111111-1",
            nombres="Docente",
            apellidos="Prueba",
            correo_institucional="docente.prueba@universidad.cl",
            activo=True
        )

        self.otro_docente = Docente.objects.create(
            usuario=self.usuario_otro,
            rut="22222222-2",
            nombres="Otro",
            apellidos="Docente",
            correo_institucional="otro.docente@universidad.cl",
            activo=True
        )

        sede = Sede.objects.create(
            nombre="Sede de Prueba",
            activo=True
        )

        campus = Campus.objects.create(
            sede=sede,
            nombre="Campus de Prueba",
            activo=True
        )

        asignatura = Asignatura.objects.create(
            codigo="HU02",
            nombre="Asignatura HU-02",
            activo=True
        )

        periodo = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="Primavera 2026",
            estado="Activo"
        )

        self.seccion = Seccion.objects.create(
            periodo=periodo,
            campus=campus,
            asignatura=asignatura,
            nrc="HU02001",
            seccion="1",
            estado="Activo"
        )

        SeccionDocente.objects.create(
            seccion=self.seccion,
            docente=self.docente
        )

        plantilla = RutaPlantilla.objects.create(
            nombre="Ruta HU-02",
            activo=True
        )

        version = RutaVersion.objects.create(
            plantilla=plantilla,
            numero_version=1,
            estado="ACTIVA"
        )

        self.ruta = SeccionRuta.objects.create(
            seccion=self.seccion,
            ruta_version=version,
            estado="EN_PROGRESO",
            porcentaje_final=0
        )

        actividad_obligatoria = RutaActividad.objects.create(
            ruta_version=version,
            etapa="Etapa de prueba",
            nombre="Actividad obligatoria",
            es_obligatoria=True,
            orden=1
        )

        actividad_opcional = RutaActividad.objects.create(
            ruta_version=version,
            etapa="Etapa de prueba",
            nombre="Actividad opcional",
            es_obligatoria=False,
            orden=2
        )

        self.actividad_obligatoria = SeccionActividad.objects.create(
            seccion_ruta=self.ruta,
            ruta_actividad=actividad_obligatoria,
            estado="PENDIENTE"
        )

        self.actividad_opcional = SeccionActividad.objects.create(
            seccion_ruta=self.ruta,
            ruta_actividad=actividad_opcional,
            estado="PENDIENTE"
        )

    def test_docente_puede_ver_su_ruta(self):
        self.client.force_login(self.usuario_docente)

        respuesta = self.client.get(
            reverse(
                "rutas:detalle_ruta_docente",
                args=[self.ruta.id]
            )
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_otro_docente_no_puede_ver_ruta_ajena(self):
        self.client.force_login(self.usuario_otro)

        respuesta = self.client.get(
            reverse(
                "rutas:detalle_ruta_docente",
                args=[self.ruta.id]
            )
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_coordinador_puede_ver_seguimiento(self):
        self.client.force_login(self.usuario_coordinador)

        respuesta = self.client.get(
            reverse("rutas:seguimiento_rutas_coordinacion")
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_coordinador_puede_ver_detalle(self):
        self.client.force_login(self.usuario_coordinador)

        respuesta = self.client.get(
            reverse(
                "rutas:detalle_ruta_coordinacion",
                args=[self.ruta.id]
            )
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_coordinador_no_puede_completar_actividad(self):
        self.client.force_login(self.usuario_coordinador)

        respuesta = self.client.post(
            reverse(
                "rutas:completar_actividad",
                args=[self.actividad_obligatoria.id]
            )
        )

        self.assertEqual(respuesta.status_code, 403)

        self.actividad_obligatoria.refresh_from_db()

        self.assertIsNone(
            self.actividad_obligatoria.completada_por_docente
        )

    def test_avance_considera_solo_obligatorias(self):
        self.actividad_opcional.completada_por_docente = self.docente
        self.actividad_opcional.estado = "COMPLETADA"
        self.actividad_opcional.save()

        recalcular_avance(self.ruta)

        self.ruta.refresh_from_db()

        self.assertEqual(self.ruta.porcentaje_final, 0)

        self.actividad_obligatoria.completada_por_docente = self.docente
        self.actividad_obligatoria.estado = "COMPLETADA"
        self.actividad_obligatoria.save()

        recalcular_avance(self.ruta)

        self.ruta.refresh_from_db()

        self.assertEqual(self.ruta.porcentaje_final, 100)

    def test_no_puede_cerrar_ruta_con_obligatorias_pendientes(self):
        self.client.force_login(self.usuario_docente)

        respuesta = self.client.post(
            reverse(
                "rutas:completar_ruta",
                args=[self.ruta.id]
            )
        )

        self.ruta.refresh_from_db()

        self.assertNotEqual(self.ruta.estado, "COMPLETADA")
        self.assertNotEqual(self.ruta.porcentaje_final, 100)
