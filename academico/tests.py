from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .services import codigo_unico, normalizar_codigo, sugerir_codigo

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
    UnidadAcademica,
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
            reverse("seccion_list")
        )

        self.assertEqual(response.status_code, 302)


    def test_docente_no_puede_consultar_planificacion(self):
        self.client.force_login(
            self.usuario_docente1
        )

        response = self.client.get(
            reverse("seccion_list")
        )

        self.assertEqual(response.status_code, 403)


    def test_coordinador_puede_consultar_planificacion(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("seccion_list")
        )

        self.assertEqual(response.status_code, 200)


    def test_listado_muestra_datos_minimos(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("seccion_list")
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
            reverse("seccion_list"),
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
            reverse("seccion_list"),
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
            reverse("seccion_list"),
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
            reverse("seccion_list"),
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
            reverse("seccion_list"),
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
            reverse("seccion_list"),
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
            reverse("seccion_list"),
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


    def test_detalle_seccion_coordinador(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse(
                "core:detalle_seccion",
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


    def test_docente_no_puede_ver_detalle_de_seccion_ajena(self):
        # docente2 no dicta la sección B.
        self.client.force_login(
            self.usuario_docente2
        )

        response = self.client.get(
            reverse(
                "core:detalle_seccion",
                args=[self.seccion_b.id],
            )
        )

        self.assertEqual(response.status_code, 403)


    def test_periodo_no_mezcla_sede_incorrecta(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("seccion_list"),
            {
                "periodo": self.otono.id,
            },
        )

        # Los nombres de campus también aparecen en el filtro, por eso
        # se compara el resultado y no el HTML completo.
        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_c.id,
            },
        )

    def test_filtro_sede_y_campus(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("seccion_list"),
            {
                "sede": self.sede_talca.id,
            },
        )

        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_c.id,
            },
        )

        response = self.client.get(
            reverse("seccion_list"),
            {
                "campus": self.campus_providencia.id,
            },
        )

        self.assertEqual(
            self.ids_resultado(response),
            {
                self.seccion_a.id,
                self.seccion_b.id,
            },
        )


    def test_listado_tiene_acciones_de_edicion(self):
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse("seccion_list")
        )

        self.assertContains(
            response,
            reverse("seccion_update", args=[self.seccion_a.id]),
        )
        self.assertContains(
            response,
            reverse("seccion_delete", args=[self.seccion_a.id]),
        )
        self.assertContains(
            response,
            reverse("core:detalle_seccion", args=[self.seccion_a.id]),
        )


    def test_detalle_coordinador_sin_botones_del_docente(self):
        # El coordinador no debe ver enlaces a páginas que le dan 403.
        self.client.force_login(
            self.coordinador
        )

        response = self.client.get(
            reverse(
                "core:detalle_seccion",
                args=[self.seccion_a.id],
            )
        )

        self.assertNotContains(
            response,
            reverse(
                "proyectos:gestionar_registro_equipos",
                args=[self.seccion_a.id],
            ),
        )
        self.assertNotContains(
            response,
            reverse(
                "proyectos:gestionar_equipos_seccion",
                args=[self.seccion_a.id],
            ),
        )
        self.assertNotContains(response, reverse("core:docente"))
        self.assertContains(response, reverse("seccion_list"))


    def test_detalle_docente_vuelve_a_mis_secciones(self):
        self.client.force_login(
            self.usuario_docente1
        )

        response = self.client.get(
            reverse(
                "core:detalle_seccion",
                args=[self.seccion_a.id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("core:docente"))
        self.assertContains(
            response,
            reverse(
                "proyectos:gestionar_equipos_seccion",
                args=[self.seccion_a.id],
            ),
        )


    def datos_seccion(self, seccion, **cambios):
        datos = {
            "nrc": seccion.nrc,
            "seccion": seccion.seccion,
            "periodo": seccion.periodo_id,
            "campus": seccion.campus_id,
            "asignatura": seccion.asignatura_id,
            "jornada": seccion.jornada or "",
            "estado": seccion.estado,
            "carreras": list(seccion.carreras.values_list("id", flat=True)),
            "docentes": list(seccion.docentes.values_list("id", flat=True)),
        }
        datos.update(cambios)
        return datos

    def test_editar_seccion_conserva_datos_de_la_planificacion(self):
        SeccionDocente.objects.filter(
            seccion=self.seccion_a, docente=self.docente1,
        ).update(tipo_contrato="Regular", capacitado_as=True)
        docente3 = Docente.objects.create(
            rut="33333333-3", nombres="Ana", apellidos="Rojas",
            correo_institucional="ana@uautonoma.cl", activo=True,
        )
        self.client.force_login(self.coordinador)

        # Se quita Ingeniería Civil Industrial y a María; se agrega a Ana.
        response = self.client.post(
            reverse("seccion_update", args=[self.seccion_a.id]),
            self.datos_seccion(
                self.seccion_a,
                horario="Lunes 10:00",
                carreras=[self.carrera_informatica.id],
                docentes=[self.docente1.id, docente3.id],
            ),
        )

        self.assertRedirects(response, reverse("seccion_list"))
        carrera = SeccionCarrera.objects.get(seccion=self.seccion_a)
        self.assertEqual(carrera.carrera, self.carrera_informatica)
        self.assertEqual(
            (carrera.nivel, carrera.declaracion_as, carrera.estudiantes_planificados),
            ("10", True, 20),
        )
        docente = SeccionDocente.objects.get(seccion=self.seccion_a, docente=self.docente1)
        self.assertEqual((docente.tipo_contrato, docente.capacitado_as), ("Regular", True))
        self.assertEqual(
            set(self.seccion_a.docentes.values_list("id", flat=True)),
            {self.docente1.id, docente3.id},
        )

    def test_seccion_jornada_de_la_lista_y_conserva_la_antigua(self):
        self.client.force_login(self.coordinador)
        url = reverse("seccion_update", args=[self.seccion_c.id])

        response = self.client.get(url)
        self.assertContains(response, '<option value="Vespertina TECH"')
        self.assertContains(response, '<option value="Vespertina" selected')

        response = self.client.post(url, self.datos_seccion(self.seccion_c, jornada="Nocturna"))
        self.assertContains(response, "Debes seleccionar una jornada de la lista.")

        self.client.post(url, self.datos_seccion(self.seccion_c, nrc=" 30001 ", horario="Martes"))
        self.seccion_c.refresh_from_db()
        self.assertEqual((self.seccion_c.jornada, self.seccion_c.horario), ("Vespertina", "Martes"))

    def test_migracion_pasa_secciones_activo_a_activa(self):
        migracion = import_module("academico.migrations.0004_seccion_estado_activa")
        Seccion.objects.filter(pk=self.seccion_b.pk).update(estado="Activo")

        migracion.pasar_a_activa(apps, None)

        self.assertEqual(
            set(Seccion.objects.values_list("estado", flat=True)),
            {"Activa"},
        )


class GestionAcademicaTestCase(TestCase):
    """Borrados con datos asociados, conservación de lo escrito y validaciones."""

    def setUp(self):
        User = get_user_model()

        grupo = Group.objects.create(name="Coordinador")
        self.coordinador = User.objects.create_user(
            username="coordinador_gestion",
            password="Coord1234",
        )
        self.coordinador.groups.add(grupo)
        self.client.force_login(self.coordinador)

        self.sede = Sede.objects.create(nombre="Sede Santiago", activo=True)
        self.campus = Campus.objects.create(
            sede=self.sede,
            nombre="Campus Providencia",
            activo=True,
        )
        self.facultad = Facultad.objects.create(nombre="Ingeniería", activo=True)
        self.otra_facultad = Facultad.objects.create(nombre="Derecho", activo=True)
        self.carrera = Carrera.objects.create(
            facultad=self.facultad,
            nombre="Ingeniería Civil Informática",
            activo=True,
        )

    def test_eliminar_con_datos_asociados_muestra_mensaje(self):
        response = self.client.post(
            reverse("sede_delete", args=[self.sede.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Sede.objects.filter(pk=self.sede.pk).exists())
        self.assertContains(
            response,
            "No se puede eliminar «Sede Santiago»: tiene registros asociados "
            "(1 campus). Desactive el registro en su lugar.",
        )

    def test_eliminar_periodo_con_secciones_sugiere_reasignar(self):
        periodo = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="Primavera 2026",
            estado="Activo",
        )
        asignatura = Asignatura.objects.create(nombre="Taller", activo=True)
        Seccion.objects.create(
            periodo=periodo,
            campus=self.campus,
            asignatura=asignatura,
            nrc="1",
            seccion="1",
            estado="Activa",
        )

        response = self.client.post(
            reverse("periodo_delete", args=[periodo.id]),
            follow=True,
        )

        self.assertContains(response, "tiene registros asociados (1 sección).")
        self.assertContains(response, "Elimine o reasigne primero esos registros.")

    def test_eliminar_sin_datos_asociados(self):
        response = self.client.post(
            reverse("facultad_delete", args=[self.otra_facultad.id]),
            follow=True,
        )

        self.assertFalse(Facultad.objects.filter(pk=self.otra_facultad.pk).exists())
        self.assertContains(response, "fue eliminado")

    def test_error_en_formulario_conserva_lo_escrito(self):
        # Correo inválido: se muestra el error y no se pierde lo escrito (RNF-USA-02).
        response = self.client.post(
            reverse("docente_create"),
            {
                "rut": "12.345.678-5",
                "nombres": "Juan",
                "apellidos": "Pérez",
                "correo_institucional": "correo-malo",
                "activo": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingresa un correo electrónico válido.")
        self.assertContains(response, 'value="Juan"')
        self.assertContains(response, 'value="Pérez"')
        self.assertContains(response, 'value="correo-malo"')
        self.assertFalse(Docente.objects.exists())

    def test_rut_docente_se_valida_y_normaliza(self):
        response = self.client.post(
            reverse("docente_create"),
            {
                "rut": "abc",
                "nombres": "Ana",
                "apellidos": "Soto",
                "correo_institucional": "ana@uautonoma.cl",
                "activo": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sin puntos y con guion, ej. 12345678-5.")
        self.assertFalse(Docente.objects.exists())

        self.client.post(
            reverse("docente_create"),
            {
                "rut": "12.345.678-5",
                "nombres": "Ana",
                "apellidos": "Soto",
                "correo_institucional": "ana@uautonoma.cl",
                "activo": "on",
            },
        )

        self.assertEqual(Docente.objects.get().rut, "12345678-5")

    def test_rut_docente_duplicado_con_otro_formato(self):
        Docente.objects.create(
            rut="12345678-5",
            nombres="Ana",
            apellidos="Soto",
            correo_institucional="ana@uautonoma.cl",
            activo=True,
        )

        response = self.client.post(
            reverse("docente_create"),
            {
                "rut": "12.345.678-5",
                "nombres": "Otra",
                "apellidos": "Persona",
                "correo_institucional": "otra@uautonoma.cl",
                "activo": "on",
            },
        )

        self.assertContains(response, "Ya existe un docente con ese RUT.")

    def test_unidad_valida_carrera_de_la_facultad(self):
        response = self.client.post(
            reverse("unidad_academica_create"),
            {
                "tipo": "Dirección de Carrera",
                "nombre": "Dirección ICI",
                "facultad": self.otra_facultad.id,
                "carrera": self.carrera.id,
                "activo": "on",
            },
        )

        self.assertContains(
            response,
            "La carrera seleccionada no pertenece a la facultad elegida.",
        )
        self.assertContains(response, 'value="Dirección ICI"')
        self.assertFalse(UnidadAcademica.objects.exists())

    def test_unidad_tipo_debe_ser_de_la_lista(self):
        response = self.client.post(
            reverse("unidad_academica_create"),
            {
                "tipo": "Cualquier cosa",
                "nombre": "Unidad",
                "facultad": self.facultad.id,
                "activo": "on",
            },
        )

        self.assertContains(response, "Debes seleccionar el tipo de unidad académica.")

        self.client.post(
            reverse("unidad_academica_create"),
            {
                "tipo": "Escuela",
                "nombre": "Escuela de Informática",
                "carrera": self.carrera.id,
                "activo": "on",
            },
        )

        # Sin facultad elegida, se toma la de la carrera.
        unidad = UnidadAcademica.objects.get()
        self.assertEqual(unidad.facultad, self.facultad)

    def test_periodo_tipo_es_la_duracion(self):
        # RF-ACA-01: anual, semestral, trimestral o bimestral.
        response = self.client.post(
            reverse("periodo_create"),
            {"anio": "2026", "tipo": "Primer semestre", "nombre": "Otoño 2026", "estado": "Activo"},
        )

        self.assertContains(response, "Debes seleccionar un tipo de período válido.")

        self.client.post(
            reverse("periodo_create"),
            {"anio": "2026", "tipo": "Semestral", "nombre": "Otoño 2026", "estado": "Activo"},
        )

        self.assertEqual(PeriodoAcademico.objects.get().tipo, "Semestral")

    def test_periodo_sin_nombre_lo_arma_con_parte_y_anio(self):
        response = self.client.get(reverse("periodo_create"))
        self.assertContains(response, '<option value="Trimestral"')
        self.assertContains(response, '<option value="Primavera (2º semestre)"')
        self.assertContains(response, '<option value="2º trimestre"')

        self.client.post(
            reverse("periodo_create"),
            {"anio": "2026", "tipo": "Semestral", "parte": "Primavera (2º semestre)", "nombre": "", "estado": "Activo"},
        )

        self.assertEqual(PeriodoAcademico.objects.get().nombre, "Primavera 2026 (2º semestre)")

    def test_periodo_trimestral_sin_nombre_indica_el_trimestre(self):
        self.client.post(
            reverse("periodo_create"),
            {"anio": "2027", "tipo": "Trimestral", "parte": "2º trimestre", "nombre": "", "estado": "Planificado"},
        )

        self.assertEqual(PeriodoAcademico.objects.get().nombre, "2º trimestre 2027")

    def test_migracion_pasa_semestres_a_semestral(self):
        migracion = import_module("academico.migrations.0003_periodo_tipo_por_duracion")
        otono = PeriodoAcademico.objects.create(
            anio=2025, tipo="Primer semestre", nombre="Otoño 2025", estado="Finalizado",
        )
        primavera = PeriodoAcademico.objects.create(
            anio=2025, tipo="Segundo semestre", nombre="Primavera 2025", estado="Finalizado",
        )
        # Ya existe el mismo año y nombre como Semestral: se conserva el valor antiguo.
        PeriodoAcademico.objects.create(
            anio=2024, tipo="Semestral", nombre="Primavera 2024", estado="Finalizado",
        )
        choque = PeriodoAcademico.objects.create(
            anio=2024, tipo="Segundo semestre", nombre="Primavera 2024", estado="Finalizado",
        )

        migracion.pasar_a_semestral(apps, None)

        for periodo in (otono, primavera, choque):
            periodo.refresh_from_db()
        self.assertEqual((otono.tipo, primavera.tipo), ("Semestral", "Semestral"))
        # El nombre conserva en qué semestre se sitúa.
        self.assertEqual(otono.nombre, "Otoño 2025 (1er semestre)")
        self.assertEqual(primavera.nombre, "Primavera 2025 (2º semestre)")
        self.assertEqual(choque.nombre, "Primavera 2024")
        self.assertEqual(choque.tipo, "Segundo semestre")

        # Al editarlo, el tipo antiguo se sigue mostrando.
        response = self.client.get(reverse("periodo_update", args=[choque.pk]))
        self.assertContains(response, '<option value="Segundo semestre"')

    def test_editar_periodo_conserva_un_tipo_antiguo(self):
        periodo = PeriodoAcademico.objects.create(
            anio=2025, tipo="Anual", nombre="Año 2025", estado="Finalizado",
        )
        url = reverse("periodo_update", args=[periodo.pk])

        response = self.client.get(url)
        self.assertContains(response, '<option value="Anual"')

        self.client.post(
            url,
            {"anio": "2025", "tipo": "Anual", "nombre": "Año 2025 (cerrado)", "estado": "Finalizado"},
        )

        periodo.refresh_from_db()
        self.assertEqual((periodo.tipo, periodo.nombre), ("Anual", "Año 2025 (cerrado)"))

    def test_nombres_repetidos_se_avisan(self):
        casos = [
            ("facultad_create", {"nombre": "  INGENIERIA ", "activo": "on"},
             "Ya existe una facultad con ese nombre."),
            ("carrera_create",
             {"nombre": "ingeniería civil informática", "facultad": self.facultad.id, "activo": "on"},
             "Ya existe una carrera con ese nombre en esta facultad."),
        ]
        Asignatura.objects.create(nombre="Taller de Integración", activo=True)
        UnidadAcademica.objects.create(
            tipo="Escuela", nombre="Escuela de Informática", facultad=self.facultad, activo=True,
        )
        casos += [
            ("asignatura_create",
             {"nombre": "taller de integración", "carreras": [self.carrera.id], "activo": "on"},
             "Ya existe una asignatura con ese nombre."),
            ("unidad_academica_create",
             {"tipo": "Escuela", "nombre": "ESCUELA DE INFORMÁTICA", "facultad": self.facultad.id, "activo": "on"},
             "Ya existe una unidad académica con ese nombre."),
        ]

        for url, datos, mensaje in casos:
            with self.subTest(url=url):
                response = self.client.post(reverse(url), datos)
                self.assertContains(response, mensaje)

        self.assertEqual(Facultad.objects.count(), 2)
        self.assertEqual(Carrera.objects.count(), 1)
        self.assertEqual(Asignatura.objects.count(), 1)
        self.assertEqual(UnidadAcademica.objects.count(), 1)

    def test_carrera_con_el_mismo_nombre_en_otra_facultad(self):
        self.client.post(
            reverse("carrera_create"),
            {"nombre": "Ingeniería Civil Informática", "facultad": self.otra_facultad.id, "activo": "on"},
        )

        self.assertEqual(Carrera.objects.filter(nombre__iexact="Ingeniería Civil Informática").count(), 2)

    def test_codigo_vacio_se_genera_al_guardar_y_no_se_repite(self):
        self.carrera.codigo = "ICI"
        self.carrera.save()

        self.client.post(
            reverse("carrera_create"),
            {"nombre": "Ingeniería Comercial e Informática", "codigo": "", "facultad": self.facultad.id, "activo": "on"},
        )
        self.client.post(
            reverse("facultad_create"),
            {"nombre": "Facultad de Ciencias de la Salud", "codigo": "", "activo": "on"},
        )

        self.assertTrue(Carrera.objects.filter(codigo="ICI2").exists())
        self.assertTrue(Facultad.objects.filter(codigo="CS").exists())

    def test_codigo_escrito_se_respeta_en_mayusculas(self):
        self.client.post(
            reverse("carrera_create"),
            {"nombre": "Derecho", "codigo": " der 01 ", "facultad": self.otra_facultad.id, "activo": "on"},
        )
        self.client.post(
            reverse("asignatura_create"),
            {"nombre": "Programación I", "codigo": "inf 101", "carreras": [self.carrera.id], "activo": "on"},
        )

        self.assertEqual(Carrera.objects.get(nombre="Derecho").codigo, "DER01")
        self.assertEqual(Asignatura.objects.get().codigo, "INF101")

    def test_formulario_nuevo_trae_datos_para_sugerir_el_codigo(self):
        self.carrera.codigo = "ICI"
        self.carrera.save()

        response = self.client.get(reverse("carrera_create"))
        self.assertContains(response, 'data-codigo-desde="nombre"')
        self.assertContains(response, "js/codigo_sugerido.js")
        self.assertContains(response, '<script id="codigos-usados" type="application/json">["ICI"]</script>')

        # Al editar se respeta el código guardado: no se sugiere otro.
        response = self.client.get(reverse("carrera_update", args=[self.carrera.id]))
        self.assertNotContains(response, "js/codigo_sugerido.js")

    def test_asignatura_sin_codigo_no_se_inventa(self):
        self.client.post(
            reverse("asignatura_create"),
            {"nombre": "Taller", "codigo": "", "carreras": [self.carrera.id], "activo": "on"},
        )

        self.assertIsNone(Asignatura.objects.get().codigo)


class CodigoSugeridoTestCase(SimpleTestCase):

    def test_iniciales_sin_palabras_vacias_ni_tildes(self):
        casos = {
            "Ingeniería Civil Informática": "ICI",
            "Ciencias de la Salud": "CS",
            "Arquitectura, Construcción y Medio Ambiente": "ACMA",
            "Facultad de Ingeniería": "INGE",
            "Derecho": "DERE",
            "Pedagogía en Educación Básica": "PEB",
            "  ": "",
        }

        for nombre, codigo in casos.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(sugerir_codigo(nombre), codigo)

    def test_normalizar_codigo(self):
        self.assertEqual(normalizar_codigo(" inf 101 "), "INF101")
        self.assertEqual(normalizar_codigo(None), "")


class CodigoUnicoTestCase(TestCase):

    def test_agrega_sufijo_si_el_codigo_existe(self):
        facultad = Facultad.objects.create(nombre="Ingeniería", activo=True)
        Carrera.objects.create(facultad=facultad, codigo="ic", nombre="Ingeniería Comercial", activo=True)
        Carrera.objects.create(facultad=facultad, codigo="IC2", nombre="Ingeniería en Construcción", activo=True)

        self.assertEqual(codigo_unico(Carrera, "Ingeniería Civil"), "IC3")
        self.assertIsNone(codigo_unico(Carrera, "de la"))
