from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

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


class PermisosTestCase(TestCase):

    def setUp(self):

        User = get_user_model()

        self.grupo_coordinador = Group.objects.create(
            name="Coordinador"
        )

        self.grupo_docente = Group.objects.create(
            name="Docente"
        )

        self.coordinador = User.objects.create_user(
            username="coordinador",
            password="Coord1234",
        )

        self.docente1_usuario = User.objects.create_user(
            username="docente1",
            password="Docente1234",
        )

        self.docente2_usuario = User.objects.create_user(
            username="docente2",
            password="Docente1234",
        )

        self.coordinador.groups.add(
            self.grupo_coordinador
        )

        self.docente1_usuario.groups.add(
            self.grupo_docente
        )

        self.docente2_usuario.groups.add(
            self.grupo_docente
        )

        self.sede = Sede.objects.create(
            nombre="Sede Santiago",
            ciudad="Santiago",
            activo=True,
        )

        self.campus = Campus.objects.create(
            sede=self.sede,
            nombre="Campus Providencia",
            activo=True,
        )

        self.facultad = Facultad.objects.create(
            codigo="FAING",
            nombre="Facultad de Ingeniería",
            activo=True,
        )

        self.carrera = Carrera.objects.create(
            facultad=self.facultad,
            codigo="ICI",
            nombre="Ingeniería Civil Informática",
            activo=True,
        )

        self.asignatura = Asignatura.objects.create(
            codigo="AS001",
            nombre="Asignatura A+S de Prueba",
            activo=True,
        )

        self.asignatura.carreras.add(
            self.carrera
        )

        self.periodo = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="Primavera 2026",
            estado="Activo",
        )

        self.docente1 = Docente.objects.create(
            usuario=self.docente1_usuario,
            rut="11111111-1",
            nombres="Docente",
            apellidos="Uno",
            correo_institucional="docente1@uautonoma.cl",
            activo=True,
        )

        self.docente2 = Docente.objects.create(
            usuario=self.docente2_usuario,
            rut="22222222-2",
            nombres="Docente",
            apellidos="Dos",
            correo_institucional="docente2@uautonoma.cl",
            activo=True,
        )

        self.seccion1 = Seccion.objects.create(
            periodo=self.periodo,
            campus=self.campus,
            asignatura=self.asignatura,
            nrc="111",
            seccion="1",
            jornada="Diurna",
            estado="Activo",
        )

        self.seccion2 = Seccion.objects.create(
            periodo=self.periodo,
            campus=self.campus,
            asignatura=self.asignatura,
            nrc="222",
            seccion="2",
            jornada="Diurna",
            estado="Activo",
        )

        SeccionDocente.objects.create(
            seccion=self.seccion1,
            docente=self.docente1,
        )

        SeccionDocente.objects.create(
            seccion=self.seccion2,
            docente=self.docente2,
        )

        SeccionCarrera.objects.create(
            seccion=self.seccion1,
            carrera=self.carrera,
        )

        SeccionCarrera.objects.create(
            seccion=self.seccion2,
            carrera=self.carrera,
        )

    def test_docente_no_puede_acceder_coordinacion(self):

        self.client.login(
            username="docente1",
            password="Docente1234",
        )

        response = self.client.get(
            reverse("core:coordinacion")
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_docente_puede_ver_su_seccion(self):

        self.client.login(
            username="docente1",
            password="Docente1234",
        )

        response = self.client.get(
            reverse(
                "core:detalle_seccion",
                args=[self.seccion1.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_docente_no_puede_ver_seccion_de_otro_docente(self):

        self.client.login(
            username="docente1",
            password="Docente1234",
        )

        response = self.client.get(
            reverse(
                "core:detalle_seccion",
                args=[self.seccion2.id],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_coordinador_puede_acceder_coordinacion(self):

        self.client.login(
            username="coordinador",
            password="Coord1234",
        )

        response = self.client.get(
            reverse("core:coordinacion")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_usuario_anonimo_es_redirigido_al_login(self):

        response = self.client.get(
            reverse("core:coordinacion")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_docente_no_puede_acceder_gestion_academica(self):
        self.client.force_login(self.docente1_usuario)

        response = self.client.get(
            reverse("home")
        )

        self.assertEqual(response.status_code, 403)


    def test_docente_no_puede_acceder_planificacion_academica(self):
        self.client.force_login(self.docente1_usuario)

        response = self.client.get(
            reverse("planificacion_list")
        )

        self.assertEqual(response.status_code, 403)


    def test_coordinador_puede_acceder_planificacion_academica(self):
        self.client.force_login(self.coordinador)

        response = self.client.get(
            reverse("planificacion_list")
        )

        self.assertEqual(response.status_code, 200)


    def test_usuario_sin_rol_no_puede_entrar_al_portal_interno(self):
        User = get_user_model()

        usuario = User.objects.create_user(
            username="sin_rol",
            password="Prueba1234",
        )

        self.client.force_login(usuario)

        response = self.client.get(
            reverse("core:inicio")
        )

        self.assertEqual(response.status_code, 403)


    def test_anonimo_no_accede_a_planificacion_academica(self):
        response = self.client.get(
            reverse("planificacion_list")
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("usuarios:login"),
            response.url,
        )

    def test_docente_no_puede_gestionar_enlaces_planificacion(self):
        self.client.force_login(self.docente1_usuario)

        response = self.client.get(
            reverse("proyectos:gestionar_enlaces")
        )

        self.assertEqual(response.status_code, 403)
