from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    Asignatura,
    AsignaturaCarrera,
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


class PlanificacionAcademicaTestCase(TestCase):

    def setUp(self):
        User = get_user_model()

        self.grupo_coordinador = Group.objects.create(
            name="Coordinador"
        )

        self.grupo_docente = Group.objects.create(
            name="Docente"
        )

        self.coordinador = User.objects.create_user(
            username="coordinador_plan",
            password="Coord1234",
        )
        self.coordinador.groups.add(
            self.grupo_coordinador
        )

        self.usuario_docente1 = User.objects.create_user(
            username="docente_plan1",
            password="Docente1234",
        )
        self.usuario_docente1.groups.add(
            self.grupo_docente
        )

        self.usuario_docente2 = User.objects.create_user(
            username="docente_plan2",
            password="Docente1234",
        )
        self.usuario_docente2.groups.add(
            self.grupo_docente
        )

        # SEDES / CAMPUS
        self.sede_santiago = Sede.objects.create(
            nombre="Sede Santiago",
            ciudad="Santiago",
            activo=True,
        )

        self.campus_providencia = Campus.objects.create(
            sede=self.sede_santiago,
            nombre="Campus Providencia",
            activo=True,
        )

        self.sede_talca = Sede.objects.create(
            nombre="Sede Talca",
            ciudad="Talca",
            activo=True,
        )

        self.campus_talca = Campus.objects.create(
            sede=self.sede_talca,
            nombre="Campus Talca",
            activo=True,
        )

        # FACULTAD / CARRERAS
        self.facultad = Facultad.objects.create(
            codigo="ING",
            nombre="Ingeniería",
            activo=True,
        )

        self.carrera_informatica = Carrera.objects.create(
            facultad=self.facultad,
            codigo="ICI",
            nombre="Ingeniería Civil Informática",
            activo=True,
        )

        self.carrera_industrial = Carrera.objects.create(
            facultad=self.facultad,
            codigo="IND",
            nombre="Ingeniería Civil Industrial",
            activo=True,
        )

        # ASIGNATURAS
        self.consultoria = Asignatura.objects.create(
            codigo="CONS",
            nombre="Consultoría de Empresas",
            activo=True,
        )

        self.desarrollo_web = Asignatura.objects.create(
            codigo="WEB",
            nombre="Desarrollo de Aplicaciones Web",
            activo=True,
        )

        AsignaturaCarrera.objects.create(
            asignatura=self.consultoria,
            carrera=self.carrera_informatica,
        )

        AsignaturaCarrera.objects.create(
            asignatura=self.consultoria,
            carrera=self.carrera_industrial,
        )

        AsignaturaCarrera.objects.create(
            asignatura=self.desarrollo_web,
            carrera=self.carrera_informatica,
        )

        # PERIODOS
        self.primavera = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Primavera",
            nombre="Primavera 2026",
            estado="Activo",
        )

        self.otono = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Otoño",
            nombre="Otoño 2026",
            estado="Activo",
        )

        # DOCENTES
        self.docente1 = Docente.objects.create(
            usuario=self.usuario_docente1,
            rut="11111111-1",
            nombres="Juan",
            apellidos="Pérez",
            correo_institucional="juan@uautonoma.cl",
            activo=True,
        )

        self.docente2 = Docente.objects.create(
            usuario=self.usuario_docente2,
            rut="22222222-2",
            nombres="María",
            apellidos="Soto",
            correo_institucional="maria@uautonoma.cl",
            activo=True,
        )

        # SECCIÓN A:
        # multicarrera + multidocente
        self.seccion_a = Seccion.objects.create(
            periodo=self.primavera,
            campus=self.campus_providencia,
            asignatura=self.consultoria,
            nrc="10001",
            seccion="01",
            jornada="Diurna",
            estado="Activa",
        )

        SeccionCarrera.objects.create(
            seccion=self.seccion_a,
            carrera=self.carrera_informatica,
            nivel="10",
            declaracion_as=True,
            estudiantes_planificados=20,
        )

        SeccionCarrera.objects.create(
            seccion=self.seccion_a,
            carrera=self.carrera_industrial,
            nivel="10",
            declaracion_as=True,
            estudiantes_planificados=15,
        )

        SeccionDocente.objects.create(
            seccion=self.seccion_a,
            docente=self.docente1,
        )

        SeccionDocente.objects.create(
            seccion=self.seccion_a,
            docente=self.docente2,
        )

        # SECCIÓN B
        self.seccion_b = Seccion.objects.create(
            periodo=self.primavera,
            campus=self.campus_providencia,
            asignatura=self.desarrollo_web,
            nrc="20001",
            seccion="02",
            jornada="Diurna",
            estado="Activa",
        )

        SeccionCarrera.objects.create(
            seccion=self.seccion_b,
            carrera=self.carrera_informatica,
        )

        SeccionDocente.objects.create(
            seccion=self.seccion_b,
            docente=self.docente1,
        )

        # SECCIÓN C: otro período y otra sede
        self.seccion_c = Seccion.objects.create(
            periodo=self.otono,
            campus=self.campus_talca,
            asignatura=self.consultoria,
            nrc="30001",
            seccion="03",
            jornada="Vespertina",
            estado="Activa",
        )

        SeccionCarrera.objects.create(
            seccion=self.seccion_c,
            carrera=self.carrera_industrial,
        )

        SeccionDocente.objects.create(
            seccion=self.seccion_c,
            docente=self.docente2,
        )


    def ids_resultado(self, response):
        return set(
            response.context["secciones"]
            .values_list("id", flat=True)
        )


    def test_anonimo_es_redirigido(self):
        response = self.client.get(
            reverse("planificacion_list")
        )

        self.assertEqual(response.status_code, 302)


    def test_docente_no_puede_consultar_planificacion(self):
        self.client.force_login(
            self.usuario_docente1
        )

        response = self.client.get(
            reverse("planificacion_list")
        )

        self.assertEqual(response.status_code, 403)


    def test_coordinador_puede_consultar_planificacion(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list")
        )

        self.assertEqual(response.status_code, 200)


    def test_listado_muestra_datos_minimos(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list")
        )

        self.assertContains(response, "10001")
        self.assertContains(response, "01")
        self.assertContains(
            response,
            "Consultoría de Empresas",
        )
        self.assertContains(
            response,
            "Ingeniería Civil Informática",
        )
        self.assertContains(response, "Juan")
        self.assertContains(response, "María")


    def test_filtro_periodo(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list"),
            {
                "periodo": self.primavera.id,
            },
        )

        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_a.id,
                self.seccion_b.id,
            },
        )


    def test_filtro_carrera(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list"),
            {
                "carrera":
                    self.carrera_informatica.id,
            },
        )

        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_a.id,
                self.seccion_b.id,
            },
        )


    def test_filtro_asignatura(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list"),
            {
                "asignatura":
                    self.desarrollo_web.id,
            },
        )

        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_b.id,
            },
        )


    def test_busqueda_nrc(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list"),
            {
                "nrc": "100",
            },
        )

        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_a.id,
            },
        )


    def test_filtro_docente(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list"),
            {
                "docente": self.docente2.id,
            },
        )

        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_a.id,
                self.seccion_c.id,
            },
        )


    def test_filtros_combinados(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list"),
            {
                "periodo": self.primavera.id,
                "carrera":
                    self.carrera_industrial.id,
                "asignatura":
                    self.consultoria.id,
                "docente": self.docente2.id,
                "nrc": "100",
            },
        )

        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_a.id,
            },
        )


    def test_multicarrera_multidocente_no_duplica_seccion(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list"),
            {
                "carrera":
                    self.carrera_informatica.id,
                "docente": self.docente1.id,
            },
        )

        ids = list(
            response.context["secciones"]
            .values_list("id", flat=True)
        )

        self.assertEqual(
            ids.count(self.seccion_a.id),
            1,
        )


    def test_detalle_planificacion(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse(
                "planificacion_detail",
                args=[self.seccion_a.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Ingeniería Civil Informática",
        )

        self.assertContains(
            response,
            "Ingeniería Civil Industrial",
        )

        self.assertContains(response, "Juan")
        self.assertContains(response, "María")


    def test_docente_no_puede_ver_detalle_planificacion(self):
        self.client.force_login(
            self.usuario_docente1
        )

        response = self.client.get(
            reverse(
                "planificacion_detail",
                args=[self.seccion_a.id],
            )
        )

        self.assertEqual(response.status_code, 403)


    def test_periodo_no_mezcla_sede_incorrecta(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("planificacion_list"),
            {
                "periodo": self.otono.id,
            },
        )

        self.assertContains(
            response,
            "Campus Talca",
        )

        self.assertContains(
            response,
            "Sede Talca",
        )

        self.assertNotContains(
            response,
            "Campus Providencia",
        )