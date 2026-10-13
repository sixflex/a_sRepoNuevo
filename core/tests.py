from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from academico.models import Asignatura, Campus, Docente, PeriodoAcademico, Seccion, Sede
from planificacion.services import _resolver_docente

from .validators import es_rut_valido, normalizar_rut, validar_rut_chileno
from academico.models import Asignatura, Campus, Docente, PeriodoAcademico, Seccion, SeccionDocente, Sede

class ValidadorRutTestCase(TestCase):

    def test_valida_y_normaliza(self):
        self.assertEqual(validar_rut_chileno("12.345.678-5"), "12345678-5")
        self.assertEqual(validar_rut_chileno("123456785"), "12345678-5")
        self.assertEqual(validar_rut_chileno("11.111.112-k"), "11111112-K")

    def test_rechaza_rut_invalido(self):
        for rut in ["", "abc", "12.345.678-9", "1"]:
            with self.assertRaises(ValidationError):
                validar_rut_chileno(rut)

        self.assertFalse(es_rut_valido("12.345.678-9"))
        self.assertTrue(es_rut_valido("12345678-5"))

    def test_normalizar_sin_validar(self):
        self.assertEqual(normalizar_rut(" 12.345.678-9 "), "12345678-9")
        self.assertEqual(normalizar_rut(""), "")

    def test_socios_reexporta_el_mismo_validador(self):
        from socios.validators import validar_rut_chileno as de_socios

        self.assertIs(de_socios, validar_rut_chileno)

    def test_planificacion_encuentra_docente_con_rut_escrito_con_puntos(self):
        docente = Docente.objects.create(
            rut="12345678-5",
            nombres="Ana",
            apellidos="Soto",
            correo_institucional="ana@uautonoma.cl",
            activo=True,
        )

        fila = SimpleNamespace(rut="12.345.678-5", correo="")

        self.assertEqual(_resolver_docente(fila), docente)


class NavegacionTestCase(TestCase):

    def setUp(self):
        User = get_user_model()

        self.coordinador = User.objects.create_user(
            username="coordinador_nav",
            password="Coord1234",
        )
        self.coordinador.groups.add(Group.objects.create(name="Coordinador"))

        self.docente = User.objects.create_user(
            username="docente_nav",
            password="Docente1234",
        )
        self.docente.groups.add(Group.objects.create(name="Docente"))

    def test_docente_entra_al_inicio_docente(self):
        self.client.force_login(self.docente)

        response = self.client.get(reverse("core:inicio"))

        self.assertRedirects(response, reverse("core:inicio_docente"))

    def test_menu_docente_distingue_inicio_y_mis_secciones(self):
        self.client.force_login(self.docente)

        response = self.client.get(reverse("core:inicio_docente"))

        self.assertContains(response, reverse("core:docente"))
        self.assertContains(response, "Mis secciones")

    def test_menu_coordinador_tiene_todas_las_secciones(self):
        self.client.force_login(self.coordinador)

        response = self.client.get(reverse("core:coordinacion"))

        for nombre in [
            "home",
            "proyectos:gestionar_enlaces",
            "core:planificacion_coordinacion",
            "seccion_list",
            "rutas:seguimiento_rutas_coordinacion",
            "cartas:listar_solicitudes_coordinacion",
            "socios:lista_coordinador",
            "socios:lista_postulaciones",
            "encuestas:lista",
        ]:
            self.assertContains(response, f'href="{reverse(nombre)}"')

    def test_menu_marca_la_seccion_activa(self):
        self.client.force_login(self.coordinador)

        response = self.client.get(reverse("socios:lista_postulaciones"))

        self.assertEqual(response.context["menu_activo"], "postulaciones")
        self.assertContains(
            response,
            f'aria-current="page"\n                                   href="{reverse("socios:lista_postulaciones")}"',
        )

        response = self.client.get(reverse("sede_create"))
        self.assertEqual(response.context["menu_activo"], "academico")

        response = self.client.get(reverse("seccion_create"))
        self.assertEqual(response.context["menu_activo"], "secciones")

    def test_panel_muestra_periodo_actual_y_pendientes(self):
        PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="Primavera 2026",
            estado="Activo",
        )

        self.client.force_login(self.coordinador)

        response = self.client.get(reverse("core:coordinacion"))

        self.assertContains(response, "<title>Inicio | Portal A+S</title>")
        self.assertContains(response, "Período actual: Primavera 2026")
        self.assertContains(response, "Pendientes")
        self.assertContains(response, reverse("socios:lista_postulaciones"))

    def test_panel_sin_periodo_activo(self):
        self.client.force_login(self.coordinador)

        response = self.client.get(reverse("core:coordinacion"))

        self.assertContains(response, "Sin período activo")
        self.assertEqual(response.context["total_periodos"], 0)

    def test_panel_cuenta_secciones_activas(self):
        sede = Sede.objects.create(nombre="Santiago", activo=True)
        campus = Campus.objects.create(sede=sede, nombre="Providencia", activo=True)
        asignatura = Asignatura.objects.create(nombre="Taller", activo=True)
        periodo = PeriodoAcademico.objects.create(
            anio=2026, tipo="Semestral", nombre="Primavera 2026", estado="Activo",
        )
        for nrc, estado in (("1", "Activa"), ("2", "Planificada"), ("3", "Finalizada")):
            Seccion.objects.create(
                periodo=periodo, campus=campus, asignatura=asignatura,
                nrc=nrc, seccion="1", estado=estado,
            )
        self.client.force_login(self.coordinador)

        response = self.client.get(reverse("core:coordinacion"))

        self.assertEqual(response.context["total_secciones"], 1)

    def test_prototipo_validar_planificacion_eliminado(self):
        # RF-ACA-04 lo resuelve la app planificacion.
        with self.assertRaises(NoReverseMatch):
            reverse("core:validar_planificacion")

    def test_pendientes_son_enlaces_a_su_listado(self):
        self.client.force_login(self.coordinador)

        response = self.client.get(reverse("core:coordinacion"))

        for nombre in [
            "cartas:listar_solicitudes_coordinacion",
            "core:planificacion_coordinacion",
            "socios:lista_postulaciones",
        ]:
            self.assertContains(response, f'href="{reverse(nombre)}" class="stretched-link"')

    def test_panel_sin_enlaces_vacios(self):
        self.client.force_login(self.coordinador)

        response = self.client.get(reverse("core:coordinacion"))

        self.assertNotContains(response, 'href="#"')
        self.assertContains(response, "Validación y Seguimiento")
        # La validación real (RF-ACA-04) está en Planificaciones recibidas
        self.assertContains(response, reverse("core:planificacion_coordinacion"))
    
class FiltroPeriodoDocenteTestCase(TestCase):
    def setUp(self):
        User = get_user_model()

        grupo, _ = Group.objects.get_or_create(name="Docente")

        self.usuario = User.objects.create_user(
            username="docente_filtro",
            password="Prueba12345"
        )
        self.usuario.groups.add(grupo)

        self.otro_usuario = User.objects.create_user(
            username="otro_docente_filtro",
            password="Prueba12345"
        )
        self.otro_usuario.groups.add(grupo)

        self.docente = Docente.objects.create(
            usuario=self.usuario,
            rut="11111111-1",
            nombres="Docente",
            apellidos="Prueba",
            correo_institucional="docente.filtro@universidad.cl",
            activo=True
        )

        self.otro_docente = Docente.objects.create(
            usuario=self.otro_usuario,
            rut="22222222-2",
            nombres="Otro",
            apellidos="Docente",
            correo_institucional="otro.filtro@universidad.cl",
            activo=True
        )

        sede = Sede.objects.create(
            nombre="Sede Filtro",
            activo=True
        )

        campus = Campus.objects.create(
            sede=sede,
            nombre="Campus Filtro",
            activo=True
        )

        asignatura = Asignatura.objects.create(
            codigo="FILTRO01",
            nombre="Asignatura Filtro",
            activo=True
        )

        self.periodo_otono = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Semestral",
            nombre="Otoño 2026 (1.º semestre)",
            estado="Activo"
        )

        self.periodo_primavera = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Semestral",
            nombre="Primavera 2026 (2.º semestre)",
            estado="Activo"
        )

        self.seccion_otono = Seccion.objects.create(
            periodo=self.periodo_otono,
            campus=campus,
            asignatura=asignatura,
            nrc="FILTRO001",
            seccion="1",
            estado="Activa"
        )

        self.seccion_primavera = Seccion.objects.create(
            periodo=self.periodo_primavera,
            campus=campus,
            asignatura=asignatura,
            nrc="FILTRO002",
            seccion="2",
            estado="Activa"
        )

        self.seccion_ajena = Seccion.objects.create(
            periodo=self.periodo_otono,
            campus=campus,
            asignatura=asignatura,
            nrc="FILTRO003",
            seccion="3",
            estado="Activa"
        )

        SeccionDocente.objects.create(
            seccion=self.seccion_otono,
            docente=self.docente
        )

        SeccionDocente.objects.create(
            seccion=self.seccion_primavera,
            docente=self.docente
        )

        SeccionDocente.objects.create(
            seccion=self.seccion_ajena,
            docente=self.otro_docente
        )

        self.client.force_login(self.usuario)

    def test_muestra_secciones_de_todos_los_periodos(self):
        respuesta = self.client.get(reverse("core:docente"))

        self.assertEqual(respuesta.status_code, 200)

        secciones = list(respuesta.context["secciones"])

        self.assertIn(self.seccion_otono, secciones)
        self.assertIn(self.seccion_primavera, secciones)
        self.assertNotIn(self.seccion_ajena, secciones)

    def test_filtra_por_primer_semestre(self):
        respuesta = self.client.get(
            reverse("core:docente"),
            {"periodo": str(self.periodo_otono.id)}
        )

        secciones = list(respuesta.context["secciones"])

        self.assertEqual(secciones, [self.seccion_otono])

    def test_filtra_por_segundo_semestre(self):
        respuesta = self.client.get(
            reverse("core:docente"),
            {"periodo": str(self.periodo_primavera.id)}
        )

        secciones = list(respuesta.context["secciones"])

        self.assertEqual(secciones, [self.seccion_primavera])

    def test_periodo_invalido_no_muestra_secciones(self):
        respuesta = self.client.get(
            reverse("core:docente"),
            {"periodo": "invalido"}
        )

        self.assertEqual(
            list(respuesta.context["secciones"]),
            []
        )

    def test_periodo_sin_secciones_asignadas_no_muestra_resultados(self):
        otro_periodo = PeriodoAcademico.objects.create(
            anio=2025,
            tipo="Semestral",
            nombre="Otoño 2025",
            estado="Activo"
        )

        respuesta = self.client.get(
            reverse("core:docente"),
            {"periodo": str(otro_periodo.id)}
        )

        self.assertEqual(
            list(respuesta.context["secciones"]),
            []
        )

    def test_filtra_por_anio(self):
        respuesta = self.client.get(
            reverse("core:docente"),
            {"anio": "2026"}
        )

        secciones = list(respuesta.context["secciones"])

        self.assertEqual(len(secciones), 2)
        self.assertNotIn(self.seccion_ajena, secciones)

    def test_selector_solo_muestra_periodos_del_docente(self):
        otro_periodo = PeriodoAcademico.objects.create(
            anio=2025,
            tipo="Semestral",
            nombre="Otoño 2025",
            estado="Activo"
        )

        respuesta = self.client.get(reverse("core:docente"))

        periodos = list(respuesta.context["periodos"])

        self.assertIn(self.periodo_otono, periodos)
        self.assertIn(self.periodo_primavera, periodos)
        self.assertNotIn(otro_periodo, periodos)
