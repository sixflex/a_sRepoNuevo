from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError

from academico.models import (
    Asignatura,
    Campus,
    Carrera,
    Docente,
    Facultad,
    PeriodoAcademico,
    Seccion,
    SeccionCarrera,
    SeccionDocente,
    Sede,
)
from rutas.models import (
    RutaActividad,
    RutaPlantilla,
    RutaVersion,
    SeccionActividad,
    SeccionRuta,
)
from rutas.services import asignar_ruta_a_seccion, asignar_ruta_as_si_corresponde
from rutas.views import recalcular_avance


class RutaDocenteTestCase(TestCase):
    def setUp(self):
        User = get_user_model()

        self.grupo_docente = Group.objects.create(name="Docente")

        self.user_docente = User.objects.create_user(
            username="docente_ruta",
            password="Docente1234",
        )
        self.user_docente.groups.add(self.grupo_docente)

        self.docente = Docente.objects.create(
            usuario=self.user_docente,
            rut="12345678-9",
            nombres="Docente",
            apellidos="Prueba",
            correo_institucional="docente_ruta@uautonoma.cl",
            activo=True,
        )

        self.sede = Sede.objects.create(nombre="Sede Santiago", activo=True)
        self.campus = Campus.objects.create(sede=self.sede, nombre="Campus Providencia", activo=True)
        self.facultad = Facultad.objects.create(nombre="Facultad de Ingeniería", activo=True)
        self.carrera = Carrera.objects.create(facultad=self.facultad, nombre="Ingeniería Civil Informática", activo=True)
        self.asignatura = Asignatura.objects.create(codigo="AS001", nombre="Asignatura A+S", activo=True)
        self.asignatura.carreras.add(self.carrera)

        self.periodo = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="Primavera 2026",
            estado="Activo",
        )

        self.plantilla = RutaPlantilla.objects.create(
            nombre="Ruta del Docente A+S",
            descripcion="Ruta 2026",
            activo=True,
        )

        self.version = RutaVersion.objects.create(
            plantilla=self.plantilla,
            numero_version=1,
            estado="BORRADOR",
        )

        for orden in range(1, 24):
            RutaActividad.objects.create(
                ruta_version=self.version,
                etapa="Etapa de prueba",
                nombre=f"Actividad {orden}",
                es_obligatoria=True,
                acepta_evidencias=orden in [11, 16, 20, 21],
                orden=orden,
            )

        self.version.estado = "ACTIVA"
        self.version.save(update_fields=["estado"])

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

        SeccionDocente.objects.create(
            seccion=seccion,
            docente=self.docente,
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
        self.assertEqual(SeccionRuta.objects.filter(seccion=seccion).count(), 1)

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

    def test_porcentaje_solo_cuenta_obligatorias(self):
        """
        Criterio de aceptación: el porcentaje cuenta solo las obligatorias.
        Las actividades opcionales completadas no alteran el porcentaje.
        """
        # Configurar 2 obligatorias y 2 opcionales para una versión simplificada
        plantilla_test = RutaPlantilla.objects.create(nombre="Ruta Test PV03", activo=True)
        version_test = RutaVersion.objects.create(plantilla=plantilla_test, numero_version=1, estado="BORRADOR")
        act_ob1 = RutaActividad.objects.create(
            ruta_version=version_test, etapa="E1", nombre="Obligatoria 1", orden=1, es_obligatoria=True
        )
        act_ob2 = RutaActividad.objects.create(
            ruta_version=version_test, etapa="E1", nombre="Obligatoria 2", orden=2, es_obligatoria=True
        )
        act_op1 = RutaActividad.objects.create(
            ruta_version=version_test, etapa="E1", nombre="Opcional 1", orden=3, es_obligatoria=False
        )
        act_op2 = RutaActividad.objects.create(
            ruta_version=version_test, etapa="E1", nombre="Opcional 2", orden=4, es_obligatoria=False
        )
        version_test.estado = "ACTIVA"
        version_test.save(update_fields=["estado"])

        seccion = self.crear_seccion("RUTA_PV03_1")
        seccion_ruta = asignar_ruta_a_seccion(seccion, version_test)

        # Inicialmente 0%
        self.assertEqual(recalcular_avance(seccion_ruta), Decimal("0.00"))

        sa_ob1 = SeccionActividad.objects.get(seccion_ruta=seccion_ruta, ruta_actividad=act_ob1)
        sa_ob2 = SeccionActividad.objects.get(seccion_ruta=seccion_ruta, ruta_actividad=act_ob2)
        sa_op1 = SeccionActividad.objects.get(seccion_ruta=seccion_ruta, ruta_actividad=act_op1)

        # Completar actividad opcional: el avance sigue en 0%
        sa_op1.completada_por_docente = self.docente
        sa_op1.save()
        self.assertEqual(recalcular_avance(seccion_ruta), Decimal("0.00"))

        # Completar una actividad obligatoria: avance es 50% (1 de 2 obligatorias)
        sa_ob1.completada_por_docente = self.docente
        sa_ob1.save()
        self.assertEqual(recalcular_avance(seccion_ruta), Decimal("50.00"))

        # Completar la segunda obligatoria: avance es 100% (2 de 2 obligatorias)
        sa_ob2.completada_por_docente = self.docente
        sa_ob2.save()
        self.assertEqual(recalcular_avance(seccion_ruta), Decimal("100.00"))

        # Docente puede completar la ruta porque todas las obligatorias están completas,
        # aunque la opcional 2 permanezca pendiente
        self.client.force_login(self.user_docente)
        url_completar = reverse("rutas:completar_ruta", kwargs={"seccion_ruta_id": seccion_ruta.id})
        resp = self.client.post(url_completar)
        self.assertEqual(resp.status_code, 302)

        seccion_ruta.refresh_from_db()
        self.assertEqual(seccion_ruta.estado, "COMPLETADA")
        self.assertEqual(seccion_ruta.porcentaje_final, Decimal("100.00"))

    def test_cambio_configuracion_sin_tocar_codigo(self):
        """
        Criterio de aceptación: cambiar la configuración en BD (ej. vía admin)
        no requiere tocar código y actualiza el cálculo del porcentaje de inmediato.
        """
        plantilla_test = RutaPlantilla.objects.create(nombre="Ruta Admin Test", activo=True)
        version_test = RutaVersion.objects.create(plantilla=plantilla_test, numero_version=1, estado="BORRADOR")
        act1 = RutaActividad.objects.create(
            ruta_version=version_test, etapa="E1", nombre="Act 1", orden=1, es_obligatoria=True
        )
        act2 = RutaActividad.objects.create(
            ruta_version=version_test, etapa="E1", nombre="Act 2", orden=2, es_obligatoria=True
        )

        version_test.estado = "ACTIVA"
        version_test.save(update_fields=["estado"])

        seccion = self.crear_seccion("RUTA_CONF_1")
        seccion_ruta = asignar_ruta_a_seccion(seccion, version_test)

        sa1 = SeccionActividad.objects.get(seccion_ruta=seccion_ruta, ruta_actividad=act1)
        sa1.completada_por_docente = self.docente
        sa1.save()

        # Con 2 obligatorias y 1 completada -> 50%
        self.assertEqual(recalcular_avance(seccion_ruta), Decimal("50.00"))

        with self.assertRaises(ValidationError):
            act2.es_obligatoria = False
            act2.save()

        # Al recalcular o visitar la ruta, ahora hay solo 1 obligatoria completada de 1 -> 100%
        self.client.force_login(self.user_docente)
        url_detalle = reverse("rutas:detalle_ruta_docente", kwargs={"seccion_ruta_id": seccion_ruta.id})
        resp = self.client.get(url_detalle)
        self.assertEqual(resp.status_code, 200)

        seccion_ruta.refresh_from_db()
        self.assertEqual(seccion_ruta.porcentaje_final, Decimal("50.00"))

    def test_subir_evidencia_valida_por_configuracion_no_por_orden_fijado(self):
        """
        Verifica que se eliminaron los órdenes fijados en código (11, 16, 20, 21):
        - Una actividad que NO tiene orden 11, 16, 20 o 21 (ej. orden 5) pero tiene acepta_evidencias=True
          permite subir evidencias.
        - Una actividad que TIENE orden 11 pero se le desmarca acepta_evidencias=False
          rechaza la subida con PermissionDenied (403).
        """
        seccion = self.crear_seccion("RUTA_EVI_1")
        seccion_ruta = asignar_ruta_as_si_corresponde(seccion)

        # Actividad con orden arbitrario (orden 5) marcada con acepta_evidencias=True
        act_5 = RutaActividad.objects.get(ruta_version=self.version, orden=5)
        act_5.acepta_evidencias = True
        act_5.save()

        sa_5 = SeccionActividad.objects.get(seccion_ruta=seccion_ruta, ruta_actividad=act_5)

        self.client.force_login(self.user_docente)
        archivo_prueba = SimpleUploadedFile("informe.pdf", b"%PDF-1.4 prueba", content_type="application/pdf")
        url_subir_5 = reverse("rutas:subir_evidencia", kwargs={"actividad_id": sa_5.id})

        resp_5 = self.client.post(url_subir_5, {"archivo": archivo_prueba, "descripcion": "Evidencia orden 5"})
        self.assertEqual(resp_5.status_code, 302)
        self.assertEqual(sa_5.evidencias.count(), 1)

        # Actividad con orden 11 a la que se le desmarca acepta_evidencias=False
        act_11 = RutaActividad.objects.get(ruta_version=self.version, orden=11)
        act_11.acepta_evidencias = False
        act_11.save()

        sa_11 = SeccionActividad.objects.get(seccion_ruta=seccion_ruta, ruta_actividad=act_11)
        url_subir_11 = reverse("rutas:subir_evidencia", kwargs={"actividad_id": sa_11.id})

        archivo_prueba_11 = SimpleUploadedFile("acuerdo.pdf", b"%PDF-1.4 prueba", content_type="application/pdf")
        resp_11 = self.client.post(url_subir_11, {"archivo": archivo_prueba_11})
        self.assertEqual(resp_11.status_code, 403)
        self.assertEqual(sa_11.evidencias.count(), 0)

        

    def test_cargar_ruta_docente_comando_pv03(self):
        self.version.estado = "BORRADOR"
        self.version.save(update_fields=["estado"])
        self.version.delete()
        call_command("cargar_ruta_docente")

        version_cargada = RutaVersion.objects.get(
            plantilla__nombre="Ruta del Docente A+S",
            numero_version=1,
        )
        actividades = RutaActividad.objects.filter(ruta_version=version_cargada)
        self.assertEqual(actividades.count(), 23)

        # Actividades con evidencia configuradas: 11, 16, 20, 21
        ordenes_evidencia = list(
            actividades.filter(acepta_evidencias=True).values_list("orden", flat=True).order_by("orden")
        )
        self.assertEqual(ordenes_evidencia, [11, 16, 20, 21])

        # Actividades opcionales: 10 y 17
        ordenes_opcionales = list(
            actividades.filter(es_obligatoria=False).values_list("orden", flat=True).order_by("orden")
        )
        self.assertEqual(ordenes_opcionales, [10, 17])

        # Recurso Canvas en actividad 1
        act_1 = actividades.get(orden=1)
        self.assertEqual(act_1.recurso_url, "https://canvas.uautonoma.cl")
