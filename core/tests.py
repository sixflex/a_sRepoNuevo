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
        self.assertIsNone(response.context["filtros"]["periodo"])
        self.assertEqual(response.context["chips"], [])

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


class PanelIndicadoresTestCase(TestCase):
    """Panel del coordinador: filtros, tarjetas, avance por carrera, satisfacción y mapa."""

    def setUp(self):
        from decimal import Decimal

        from django.utils import timezone

        from academico.models import Carrera, Facultad, SeccionCarrera, SeccionDocente
        from proyectos.models import Equipo, IntegranteEquipo
        from rutas.models import RutaActividad, RutaPlantilla, RutaVersion, SeccionActividad, SeccionRuta
        from socios.models import Comuna, ParticipacionSocio, SocioComunitario

        User = get_user_model()
        self.coordinador = User.objects.create_user(username="coord_panel", password="Coord1234")
        self.coordinador.groups.add(Group.objects.create(name="Coordinador"))

        sede = Sede.objects.create(nombre="Santiago", activo=True)
        self.campus = Campus.objects.create(sede=sede, nombre="Providencia", activo=True)
        self.otono = PeriodoAcademico.objects.create(
            anio=2026, tipo="Semestral", nombre="Otoño 2026 (1er semestre)", estado="Finalizado",
        )
        self.primavera = PeriodoAcademico.objects.create(
            anio=2026, tipo="Semestral", nombre="Primavera 2026 (2º semestre)", estado="Activo",
        )
        facultad = Facultad.objects.create(nombre="Ingeniería", activo=True)
        self.informatica = Carrera.objects.create(facultad=facultad, nombre="Informática", activo=True)
        self.industrial = Carrera.objects.create(facultad=facultad, nombre="Industrial", activo=True)

        version = RutaVersion.objects.create(
            plantilla=RutaPlantilla.objects.create(nombre="Ruta A+S", activo=True),
            numero_version=1, estado="VIGENTE",
        )
        obligatorias = [
            RutaActividad.objects.create(
                ruta_version=version, etapa="Inicio", nombre=f"Actividad {n}", es_obligatoria=True, orden=n,
            )
            for n in range(1, 5)
        ]
        opcional = RutaActividad.objects.create(
            ruta_version=version, etapa="Cierre", nombre="Opcional", es_obligatoria=False, orden=9,
        )

        def seccion(nrc, carrera, completadas, periodo=None, docente="Ana"):
            seccion = Seccion.objects.create(
                periodo=periodo or self.primavera, campus=self.campus,
                asignatura=Asignatura.objects.create(nombre=f"Asignatura {nrc}", activo=True),
                nrc=nrc, seccion="1", estado="Activa",
            )
            SeccionCarrera.objects.create(
                seccion=seccion, carrera=carrera, declaracion_as=True, estudiantes_planificados=30,
            )
            profesor = Docente.objects.create(
                rut=f"{nrc}-1", nombres=docente, apellidos="Pérez",
                correo_institucional=f"{nrc}@uautonoma.cl", activo=True,
            )
            SeccionDocente.objects.create(seccion=seccion, docente=profesor)
            ruta = SeccionRuta.objects.create(
                seccion=seccion, ruta_version=version, estado="EN_PROGRESO", porcentaje_final=Decimal("0"),
            )
            # La opcional completada no debe subir el avance (RF-RUT-03).
            for indice, actividad in enumerate(obligatorias):
                SeccionActividad.objects.create(
                    seccion_ruta=ruta, ruta_actividad=actividad, estado="PENDIENTE",
                    completada_por_docente=profesor if indice < completadas else None,
                )
            SeccionActividad.objects.create(
                seccion_ruta=ruta, ruta_actividad=opcional, estado="COMPLETADA",
                completada_por_docente=profesor,
            )
            return seccion

        self.seccion_informatica = seccion("100", self.informatica, completadas=1)
        seccion("200", self.industrial, completadas=4, docente="Beto")
        seccion("300", self.informatica, completadas=0, periodo=self.otono)

        equipo = Equipo.objects.create(
            seccion=self.seccion_informatica, numero_grupo=1,
            informante_nombre="Inf", informante_correo="inf@uautonoma.cl", estado="ACTIVO",
        )
        for n in range(3):
            IntegranteEquipo.objects.create(
                equipo=equipo, rut=f"1{n}-1", nombres="E", apellidos=str(n),
                correo_institucional=f"e{n}@uautonoma.cl",
            )

        comuna = Comuna.objects.create(
            nombre="Providencia", region="RM", activo=True, lat_centro=-33.43, lon_centro=-70.61,
        )
        for nombre in ("Junta Vecinos", "Cesfam"):
            socio = SocioComunitario.objects.create(
                nombre_organizacion=nombre, comuna=comuna, estado_revision="APROBADO",
                es_provisional=False, activo=True, fecha_creacion=timezone.now(),
            )
            ParticipacionSocio.objects.create(
                socio=socio, equipo=None, seccion=self.seccion_informatica, periodo=self.primavera,
                carrera=self.informatica, origen="HISTORICO",
            )
        self.client.force_login(self.coordinador)

    def panel(self, **parametros):
        return self.client.get(reverse("core:coordinacion"), parametros)

    def test_sin_filtros_parte_en_el_periodo_vigente(self):
        response = self.panel()

        self.assertEqual(response.context["filtros"]["periodo"], self.primavera.id)
        self.assertEqual([chip["etiqueta"] for chip in response.context["chips"]], [self.primavera.nombre])
        self.assertContains(response, 'aria-label="Quitar filtro Primavera 2026 (2º semestre)"')

    def test_tarjetas_del_periodo_y_variacion(self):
        tarjetas = {t["etiqueta"]: t for t in self.panel().context["tarjetas"]}

        self.assertEqual(tarjetas["Asignaturas A+S"]["valor"], 2)
        self.assertEqual(tarjetas["Docentes participantes"]["valor"], 2)
        self.assertEqual(tarjetas["Carreras participantes"]["valor"], 2)
        # Integrantes registrados en equipos, no los planificados.
        self.assertEqual(tarjetas["Estudiantes participantes"]["valor"], 3)
        self.assertEqual(tarjetas["Socios comunitarios"]["valor"], 2)
        self.assertIn("2 participaciones", tarjetas["Socios comunitarios"]["detalle"])
        # Otoño tenía 1 asignatura: +1 vs período anterior.
        self.assertEqual(tarjetas["Asignaturas A+S"]["detalle"], "+1 vs período anterior")

    def test_quitar_todos_los_filtros_muestra_todo(self):
        response = self.panel(f="1")

        self.assertIsNone(response.context["filtros"]["periodo"])
        tarjetas = {t["etiqueta"]: t for t in response.context["tarjetas"]}
        self.assertEqual(tarjetas["Asignaturas A+S"]["valor"], 3)

    def test_avance_por_carrera_de_menor_a_mayor_solo_obligatorias(self):
        avance = self.panel().context["avance_carreras"]

        self.assertEqual([c["carrera"] for c in avance], ["Informática", "Industrial"])
        self.assertEqual(avance[0]["porcentaje"], 25)
        self.assertEqual(avance[0]["nivel"]["texto"], "Bajo")
        self.assertEqual(avance[1]["porcentaje"], 100)
        self.assertEqual(avance[1]["nivel"]["texto"], "Alto")
        docente = avance[0]["docentes"][0]
        self.assertEqual(docente["pendientes"], 3)
        self.assertFalse(docente["cerrada"])

    def test_filtro_por_carrera(self):
        response = self.panel(f="1", periodo=self.primavera.id, carrera=self.industrial.id)

        self.assertEqual([c["carrera"] for c in response.context["avance_carreras"]], ["Industrial"])
        self.assertEqual(len(response.context["chips"]), 2)

    def test_mapa_agrupa_por_comuna_sin_direcciones(self):
        mapa = self.panel().context["mapa"]

        self.assertEqual(len(mapa["puntos"]), 1)
        punto = mapa["puntos"][0]
        self.assertEqual((punto["comuna"], punto["socios"]), ("Providencia", 2))
        self.assertEqual(punto["carreras"], ["Informática"])
        self.assertEqual(punto["anios"], [2026])
        self.assertNotIn("direccion", punto)

    def test_satisfaccion_vacia_no_muestra_cero(self):
        response = self.panel()

        self.assertFalse(response.context["satisfaccion"]["hay_datos"])
        self.assertContains(response, "Aún no hay respuestas de las encuestas de evaluación")

    def test_satisfaccion_porcentaje_de_4_y_5_y_promedio_por_dimension(self):
        from django.utils import timezone

        from encuestas.definiciones import evaluaciones
        from encuestas.models import RespuestaFormulario, RespuestaPregunta
        from encuestas.semillas import crear_formulario

        version = crear_formulario(evaluaciones.DOCENTES)
        generales = list(
            version.preguntas.filter(configuracion_json__valoracion_general=True).order_by("orden")
        )
        aprendizaje = list(version.preguntas.filter(configuracion_json__dimension="aprendizaje"))
        self.assertEqual(len(generales), 6)

        for valores in ([5, 5, 4, 4, 2, 1], [5, 4, 4, 3, 5, 5]):
            respuesta = RespuestaFormulario.objects.create(
                version=version, fecha_envio=timezone.now(), origen="ENLACE",
                es_historica=False, estado_registro="CONFIRMADA", periodo=self.primavera,
            )
            for pregunta, valor in zip(generales, valores):
                RespuestaPregunta.objects.create(respuesta=respuesta, pregunta=pregunta, valor_escala=valor)
            for pregunta in aprendizaje:
                RespuestaPregunta.objects.create(respuesta=respuesta, pregunta=pregunta, valor_escala=4)

        satisfaccion = self.panel().context["satisfaccion"]
        docentes = satisfaccion["anillos"][1]
        # 9 de 12 respuestas con 4 o 5.
        self.assertEqual(docentes["porcentaje"], 75.0)
        self.assertEqual(docentes["personas"], 2)
        self.assertEqual(docentes["pregunta"], 18)
        self.assertIsNone(satisfaccion["anillos"][0]["porcentaje"])
        self.assertEqual(satisfaccion["tabla"][0]["valores"], [None, 4.0, None])
