from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from academico.models import (Asignatura,Campus,Carrera,Docente,Facultad,PeriodoAcademico,Seccion,SeccionCarrera,SeccionDocente,Sede,UnidadAcademica,)
from auditoria.models import AuditoriaCambio
from auditoria.services import registrar_auditoria
from planificacion.email_service import enviar_correo_planificacion
from planificacion.forms import DocenteFilaForm, FilaPlanificacionForm
from planificacion.models import (FilaPlanificacion,FilaPlanificacionDocente,Planificacion,PlanificacionEnlace,PlanificacionError,)
from planificacion.services import validar_y_consolidar_planificacion


class PlanificacionHU01TestCase(TestCase):

    def setUp(self):
        User = get_user_model()

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
            codigo="FAING-HU01",
            nombre="Facultad de Ingeniería",
            activo=True,
        )

        self.carrera = Carrera.objects.create(
            facultad=self.facultad,
            codigo="ICI-HU01",
            nombre="Ingeniería Civil Informática",
            activo=True,
        )

        self.asignatura = Asignatura.objects.create(
            codigo="INF-HU01",
            nombre="Proyecto A+S",
            activo=True,
        )

        self.asignatura.carreras.add(self.carrera)

        self.periodo = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="Primavera 2026",
            estado="Activo",
        )

        self.unidad = UnidadAcademica.objects.create(
            facultad=self.facultad,
            carrera=self.carrera,
            tipo="Carrera",
            nombre="Ingeniería Civil Informática",
            correo_oficial="ici@uautonoma.cl",
            activo=True,
        )

        self.usuario_docente = User.objects.create_user(
            username="docente_hu01",
            password="Prueba1234",
        )

        self.docente = Docente.objects.create(
            usuario=self.usuario_docente,
            rut="12345678-9",
            nombres="Docente",
            apellidos="Prueba",
            correo_institucional="docente.hu01@uautonoma.cl",
            activo=True,
        )

        self.enlace = PlanificacionEnlace.objects.create(
            unidad_academica=self.unidad,
            campus=self.campus,
            periodo=self.periodo,
            destinatario_nombre="Director de Carrera",
            destinatario_correo="director@uautonoma.cl",
            fecha_emision=timezone.now(),
            fecha_expiracion=timezone.now() + timedelta(days=7),
            activo=True,
        )

        self.planificacion = Planificacion.objects.create(
            enlace=self.enlace,
            estado="BORRADOR",
            filas_recibidas=0,
            filas_aceptadas=0,
            filas_observadas=0,
        )

    def crear_fila_valida(self, nrc="12345", numero_fila=1):
        fila = FilaPlanificacion.objects.create(
            planificacion=self.planificacion,
            numero_fila=numero_fila,
            facultad_texto=self.facultad.nombre,
            carrera_texto=self.carrera.nombre,
            declaracion_as=True,
            nrc=nrc,
            campus_texto=self.campus.nombre,
            seccion="1",
            asignatura_texto=self.asignatura.nombre,
            nivel="5",
            jornada="Diurna",
            horario="Lunes 10:00 - 12:00",
            estudiantes_planificados=30,
            posible_socio_texto="Fundación de prueba",
            estado_validacion="PENDIENTE",
        )

        FilaPlanificacionDocente.objects.create(
            fila=fila,
            rut=self.docente.rut,
            nombre="Docente Prueba",
            tipo_contrato="Jornada completa",
            capacitado_as=True,
            correo=self.docente.correo_institucional,
            telefono="912345678",
        )

        return fila

    def test_fila_valida_se_consolida(self):
        fila = self.crear_fila_valida()

        validar_y_consolidar_planificacion(
            self.planificacion
        )

        fila.refresh_from_db()
        self.planificacion.refresh_from_db()

        self.assertEqual(
            fila.estado_validacion,
            "ACEPTADA",
        )

        self.assertIsNotNone(
            fila.seccion_resultante
        )

        self.assertEqual(
            self.planificacion.filas_recibidas,
            1,
        )

        self.assertEqual(
            self.planificacion.filas_aceptadas,
            1,
        )

        self.assertEqual(
            self.planificacion.filas_observadas,
            0,
        )

        self.assertTrue(
            Seccion.objects.filter(
                periodo=self.periodo,
                nrc="12345",
            ).exists()
        )

    def test_fila_valida_crea_relaciones_academicas(self):
        fila = self.crear_fila_valida()

        validar_y_consolidar_planificacion(
            self.planificacion
        )

        fila.refresh_from_db()

        seccion = fila.seccion_resultante

        self.assertIsNotNone(seccion)

        self.assertTrue(
            SeccionCarrera.objects.filter(
                seccion=seccion,
                carrera=self.carrera,
            ).exists()
        )

        self.assertTrue(
            SeccionDocente.objects.filter(
                seccion=seccion,
                docente=self.docente,
            ).exists()
        )

    def test_nrc_duplicado_queda_observado(self):
        Seccion.objects.create(
            periodo=self.periodo,
            campus=self.campus,
            asignatura=self.asignatura,
            nrc="99999",
            seccion="1",
            jornada="Diurna",
            estado="Activo",
        )

        fila = self.crear_fila_valida(
            nrc="99999",
        )

        validar_y_consolidar_planificacion(
            self.planificacion
        )

        fila.refresh_from_db()
        self.planificacion.refresh_from_db()

        self.assertEqual(
            fila.estado_validacion,
            "OBSERVADA",
        )

        self.assertEqual(
            self.planificacion.filas_aceptadas,
            0,
        )

        self.assertEqual(
            self.planificacion.filas_observadas,
            1,
        )

        self.assertTrue(
            PlanificacionError.objects.filter(
                fila=fila,
                codigo="NRC_DUPLICADO",
            ).exists()
        )

    def test_docente_inexistente_queda_observado(self):
        fila = FilaPlanificacion.objects.create(
            planificacion=self.planificacion,
            numero_fila=1,
            facultad_texto=self.facultad.nombre,
            carrera_texto=self.carrera.nombre,
            declaracion_as=True,
            nrc="77777",
            campus_texto=self.campus.nombre,
            seccion="1",
            asignatura_texto=self.asignatura.nombre,
            nivel="5",
            jornada="Diurna",
            estudiantes_planificados=20,
            estado_validacion="PENDIENTE",
        )

        FilaPlanificacionDocente.objects.create(
            fila=fila,
            rut="99999999-9",
            nombre="Docente inexistente",
            correo="noexiste@uautonoma.cl",
        )

        validar_y_consolidar_planificacion(
            self.planificacion
        )

        fila.refresh_from_db()
        self.planificacion.refresh_from_db()

        self.assertEqual(
            fila.estado_validacion,
            "OBSERVADA",
        )

        self.assertIsNone(
            fila.seccion_resultante
        )

        self.assertEqual(
            self.planificacion.filas_observadas,
            1,
        )

        self.assertTrue(
            PlanificacionError.objects.filter(
                fila=fila,
                codigo="DOCENTE_NO_ENCONTRADO",
            ).exists()
        )

    def test_datos_consolidados_coinciden_con_planificacion(self):
        fila = self.crear_fila_valida()

        validar_y_consolidar_planificacion(
            self.planificacion
        )

        fila.refresh_from_db()

        seccion = fila.seccion_resultante

        self.assertEqual(
            seccion.periodo,
            self.periodo,
        )

        self.assertEqual(
            seccion.campus,
            self.campus,
        )

        self.assertEqual(
            seccion.asignatura,
            self.asignatura,
        )

        self.assertEqual(
            seccion.nrc,
            "12345",
        )

        self.assertEqual(
            seccion.estado,
            "Activa",
        )

        self.assertIsNotNone(
            seccion.fecha_consolidacion
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="portal-as@uautonoma.cl",
    )
    def test_formulario_tabular_usa_listas(self):
        # RNF-USA-03: facultad, carrera, nivel, jornada y tipo de contrato
        # se eligen de una lista; se sigue enviando el mismo texto.
        response = self.client.get(
            reverse("planificacion:formulario_tabular_as", kwargs={"token": self.enlace.token})
        )

        self.assertContains(response, '<optgroup label="Facultad de Ingeniería">')
        self.assertContains(response, '<option value="Ingeniería Civil Informática"')
        self.assertContains(response, '<option value="Vespertina TECH">')
        self.assertContains(response, '<option value="Adjunto">')
        # Formulario público: sin la barra superior del portal.
        self.assertNotContains(response, "navbar-sistema")

    def test_formulario_tabular_conserva_valores_fuera_de_la_lista(self):
        form = FilaPlanificacionForm(
            instance=FilaPlanificacion(carrera_texto="Carrera Antigua", jornada="Nocturna", nivel="Nivel 3"),
        )

        self.assertIn('<option value="Carrera Antigua" selected>', str(form["carrera_texto"]))
        self.assertIn('<option value="Nocturna" selected>', str(form["jornada"]))
        self.assertIn('<option value="Nivel 3" selected>', str(form["nivel"]))

        docente = DocenteFilaForm(initial={"tipo_contrato": "Honorarios"})
        self.assertIn('<option value="Honorarios" selected>', str(docente["tipo_contrato"]))

    def test_envio_correo_planificacion(self):
        request = RequestFactory().get("/")

        enviado = enviar_correo_planificacion(
            request,
            self.enlace,
        )

        self.assertTrue(enviado)

        self.assertEqual(
            len(mail.outbox),
            1,
        )

        correo = mail.outbox[0]

        self.assertEqual(
            correo.to,
            [self.enlace.destinatario_correo],
        )

        self.assertEqual(
            correo.subject,
            "Solicitud de planificación académica A+S",
        )

        self.assertIn(
            str(self.enlace.token),
            correo.body,
        )

        self.assertIn(
            self.unidad.nombre,
            correo.body,
        )

        self.assertIn(
            self.campus.nombre,
            correo.body,
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="portal-as@uautonoma.cl",
    )
    def test_reenvio_correo_planificacion(self):
        request = RequestFactory().get("/")

        enviado = enviar_correo_planificacion(
            request,
            self.enlace,
            reenvio=True,
        )

        self.assertTrue(enviado)

        self.assertEqual(
            len(mail.outbox),
            1,
        )

        correo = mail.outbox[0]

        self.assertEqual(
            correo.subject,
            "Reenvío de planificación académica A+S",
        )

        self.assertIn(
            str(self.enlace.token),
            correo.body,
        )

        self.assertEqual(
            correo.to,
            [self.enlace.destinatario_correo],
        )

    def test_registro_auditoria(self):
        User = get_user_model()

        coordinador = User.objects.create_user(
            username="coordinador_auditoria",
            password="Prueba1234",
        )

        request = RequestFactory().post("/")

        request.user = coordinador
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        registro = registrar_auditoria(
            request=request,
            entidad="PlanificacionEnlace",
            entidad_id=self.enlace.id,
            accion="REENVIAR_ENLACE",
            valores_anteriores={
                "activo": True,
            },
            valores_nuevos={
                "correo": self.enlace.destinatario_correo,
            },
        )

        self.assertIsNotNone(
            registro.id
        )

        self.assertEqual(
            registro.usuario,
            coordinador,
        )

        self.assertEqual(
            registro.entidad,
            "PlanificacionEnlace",
        )

        self.assertEqual(
            registro.entidad_id,
            str(self.enlace.id),
        )

        self.assertEqual(
            registro.accion,
            "REENVIAR_ENLACE",
        )

        self.assertEqual(
            registro.ip,
            "127.0.0.1",
        )

        self.assertEqual(
            registro.valores_anteriores_json,
            {
                "activo": True,
            },
        )

        self.assertEqual(
            registro.valores_nuevos_json,
            {
                "correo": self.enlace.destinatario_correo,
            },
        )

        self.assertTrue(
            AuditoriaCambio.objects.filter(
                entidad="PlanificacionEnlace",
                entidad_id=str(self.enlace.id),
                accion="REENVIAR_ENLACE",
            ).exists()
        )

    def test_flujo_integral_envio_final(self):
        url = reverse(
            "planificacion:formulario_tabular_as",
            kwargs={
                "token": self.enlace.token,
            },
        )

        datos = {
            "enviar_final": "1",
            "filas-TOTAL_FORMS": "1",
            "filas-INITIAL_FORMS": "0",
            "filas-MIN_NUM_FORMS": "0",
            "filas-MAX_NUM_FORMS": "1000",
            "filas-0-facultad_texto": self.facultad.nombre,
            "filas-0-carrera_texto": self.carrera.nombre,
            "filas-0-declaracion_as": "on",
            "filas-0-nrc": "HU01-100",
            "filas-0-seccion": "1",
            "filas-0-asignatura_texto": self.asignatura.nombre,
            "filas-0-nivel": "5",
            "filas-0-jornada": "Diurna",
            "filas-0-horario_0": ["Lu", "Ju"],
            "filas-0-horario_1": "10:00",
            "filas-0-estudiantes_planificados": "30",
            "socios-0-TOTAL_FORMS": "1",
            "socios-0-INITIAL_FORMS": "0",
            "socios-0-0-nombre": "Fundación de prueba",
            "docentes-0-TOTAL_FORMS": "1",
            "docentes-0-INITIAL_FORMS": "0",
            "docentes-0-MIN_NUM_FORMS": "0",
            "docentes-0-MAX_NUM_FORMS": "1000",
            "docentes-0-0-rut": self.docente.rut,
            "docentes-0-0-nombre": "Docente Prueba",
            "docentes-0-0-tipo_contrato": "Jornada completa",
            "docentes-0-0-capacitado_as": "true",
            "docentes-0-0-correo": self.docente.correo_institucional,
            "docentes-0-0-telefono": "912345678",
        }

        self.client.post(
            url,
            data=datos,
        )

        self.planificacion.refresh_from_db()

        self.assertEqual(
            self.planificacion.estado,
            "FINAL",
        )

        self.assertIsNotNone(
            self.planificacion.fecha_envio_final
        )

        self.assertEqual(
            self.planificacion.filas_recibidas,
            1,
        )

        self.assertEqual(
            self.planificacion.filas_aceptadas,
            1,
        )

        self.assertEqual(
            self.planificacion.filas_observadas,
            0,
        )

        fila = self.planificacion.filas.get(
            numero_fila=1
        )

        self.assertEqual(
            fila.estado_validacion,
            "ACEPTADA",
        )

        self.assertIsNotNone(
            fila.seccion_resultante
        )
        self.assertEqual(fila.horario, "Lunes, Jueves 10:00")
        self.assertEqual(fila.seccion_resultante.horario, "Lunes, Jueves 10:00")
        self.assertEqual(fila.posible_socio_texto, "Fundación de prueba")

        self.assertTrue(
            Seccion.objects.filter(
                periodo=self.periodo,
                nrc="HU01-100",
            ).exists()
        )

        self.assertTrue(
            AuditoriaCambio.objects.filter(
                entidad="Planificacion",
                entidad_id=str(self.planificacion.id),
                accion="ENVIO_FINAL_PLANIFICACION",
            ).exists()
        )

        cantidad_secciones = Seccion.objects.filter(
            periodo=self.periodo,
            nrc="HU01-100",
        ).count()

        self.client.post(
            url,
            data=datos,
        )

        self.planificacion.refresh_from_db()

        self.assertEqual(
            self.planificacion.estado,
            "FINAL",
        )

        self.assertEqual(
            Seccion.objects.filter(
                periodo=self.periodo,
                nrc="HU01-100",
            ).count(),
            cantidad_secciones,
        )



class HorarioYSociosPlanificacionTestCase(TestCase):
    """Subtareas 2.1 y 2.2: horario por días y socios opcionales en la planilla de Dirección."""

    setUp_base = PlanificacionHU01TestCase.setUp

    def setUp(self):
        self.setUp_base()
        self.url = reverse("planificacion:formulario_tabular_as", kwargs={"token": self.enlace.token})

    def datos(self, boton="guardar_borrador", dias=("Lu", "Mi"), hora="08:30", socios=()):
        datos = {
            boton: "1",
            "filas-TOTAL_FORMS": "1",
            "filas-INITIAL_FORMS": "0",
            "filas-MIN_NUM_FORMS": "0",
            "filas-MAX_NUM_FORMS": "1000",
            "filas-0-facultad_texto": self.facultad.nombre,
            "filas-0-carrera_texto": self.carrera.nombre,
            "filas-0-declaracion_as": "on",
            "filas-0-nrc": "HOR-100",
            "filas-0-seccion": "1",
            "filas-0-asignatura_texto": self.asignatura.nombre,
            "filas-0-nivel": "5",
            "filas-0-jornada": "Diurna",
            "filas-0-horario_0": list(dias),
            "filas-0-horario_1": hora,
            "filas-0-horario_2": "",
            "filas-0-estudiantes_planificados": "30",
            "docentes-0-TOTAL_FORMS": "1",
            "docentes-0-INITIAL_FORMS": "0",
            "docentes-0-MIN_NUM_FORMS": "0",
            "docentes-0-MAX_NUM_FORMS": "1000",
            "docentes-0-0-rut": self.docente.rut,
            "docentes-0-0-nombre": "Docente Prueba",
            "docentes-0-0-correo": self.docente.correo_institucional,
            "socios-0-TOTAL_FORMS": str(len(socios)),
            "socios-0-INITIAL_FORMS": "0",
            "socios-0-MIN_NUM_FORMS": "0",
            "socios-0-MAX_NUM_FORMS": "1000",
        }
        for i, socio in enumerate(socios):
            for campo, valor in socio.items():
                datos[f"socios-0-{i}-{campo}"] = valor
        return datos

    def fila(self):
        return FilaPlanificacion.objects.get(planificacion=self.planificacion, nrc="HOR-100")

    def test_textos_de_horario_y_socios(self):
        from datetime import time
        from planificacion.textos import leer_horario, leer_socios, texto_horario, texto_socios

        self.assertEqual(texto_horario(["Mi", "Lu"], time(8, 30)), "Lunes, Miércoles 08:30")
        self.assertEqual(leer_horario("Lunes, Miércoles 08:30"), (["Lu", "Mi"], "08:30"))
        self.assertEqual(leer_horario("Lu, Mi 08:30"), (["Lu", "Mi"], "08:30"))
        self.assertIsNone(leer_horario("Lunes 10:00 - 12:00"))
        self.assertEqual(
            texto_socios([{"nombre": "Junta | Norte", "correo": "", "rubro": "Barrio"}, {"nombre": "", "correo": "", "rubro": ""}]),
            "Junta / Norte |  | Barrio",
        )
        self.assertEqual(leer_socios("Fundación antigua"), [{"nombre": "Fundación antigua", "correo": "", "rubro": ""}])
        self.assertEqual(leer_socios("Por definir"), [])

    def test_marcar_dias_y_hora_guarda_el_texto_y_el_borrador_lo_vuelve_a_marcar(self):
        self.client.post(self.url, self.datos())

        self.assertEqual(self.fila().horario, "Lunes, Miércoles 08:30")
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="Lu" id="id_filas-0-horario_0_0" checked')
        self.assertContains(respuesta, 'value="Mi" id="id_filas-0-horario_0_2" checked')
        self.assertNotContains(respuesta, 'value="Ma" id="id_filas-0-horario_0_1" checked')
        self.assertContains(respuesta, 'value="08:30"')

    def test_hora_invalida_muestra_error_junto_al_campo(self):
        respuesta = self.client.post(self.url, self.datos(hora="25:99"))

        self.assertContains(respuesta, "Ingrese una hora válida")
        self.assertFalse(FilaPlanificacion.objects.filter(nrc="HOR-100").exists())

    def test_dias_sin_hora_pide_la_hora(self):
        respuesta = self.client.post(self.url, self.datos(hora=""))

        self.assertContains(respuesta, "Ingrese la hora de inicio")

    def test_horario_antiguo_se_muestra_y_no_se_pierde(self):
        form = FilaPlanificacionForm(instance=FilaPlanificacion(horario="Lunes 10:00 - 12:00"))
        html = str(form["horario"])

        self.assertIn("Guardado: Lunes 10:00 - 12:00", html)
        self.assertIn('value="Lunes 10:00 - 12:00"', html)

        datos = self.datos(dias=(), hora="")
        datos["filas-0-horario_2"] = "Lunes 10:00 - 12:00"
        self.client.post(self.url, datos)
        self.assertEqual(self.fila().horario, "Lunes 10:00 - 12:00")

    def test_envio_final_lleva_el_horario_a_la_seccion(self):
        self.client.post(self.url, self.datos(boton="enviar_final"))

        self.assertEqual(self.fila().seccion_resultante.horario, "Lunes, Miércoles 08:30")

    def test_socios_opcionales_se_guardan_y_el_borrador_los_conserva(self):
        socios = [
            {"nombre": "Almacén Doña Rosa", "correo": "rosa@almacen.cl", "rubro": "Alimentación"},
            {"nombre": "Taller Mecánico", "correo": "", "rubro": ""},
        ]
        self.client.post(self.url, self.datos(socios=socios))

        self.assertEqual(
            self.fila().posible_socio_texto,
            "Almacén Doña Rosa | rosa@almacen.cl | Alimentación\nTaller Mecánico",
        )
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="Almacén Doña Rosa"')
        self.assertContains(respuesta, 'value="rosa@almacen.cl"')
        self.assertContains(respuesta, 'value="Taller Mecánico"')
        self.assertNotContains(respuesta, "Posible socio comunitario</th>")

    def test_se_puede_enviar_sin_socios(self):
        self.client.post(self.url, self.datos(boton="enviar_final", socios=[{"nombre": "", "correo": "", "rubro": ""}]))

        self.planificacion.refresh_from_db()
        self.assertEqual(self.planificacion.estado, "FINAL")
        self.assertIsNone(self.fila().posible_socio_texto)

    def test_socio_quitado_no_se_guarda(self):
        socios = [{"nombre": "Se quita", "correo": "", "rubro": "", "DELETE": "on"}]
        self.client.post(self.url, self.datos(socios=socios))

        self.assertIsNone(self.fila().posible_socio_texto)

    def test_la_casilla_de_socio_solo_aparece_al_presionar_el_boton(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, "Agregar socio (opcional)")
        self.assertContains(respuesta, 'name="socios-0-TOTAL_FORMS" value="0"')
        self.assertNotContains(respuesta, 'name="socios-0-0-nombre"')

    def test_correo_invalido_o_texto_muy_largo_muestra_error(self):
        respuesta = self.client.post(self.url, self.datos(socios=[{"nombre": "X", "correo": "no-es-correo"}]))
        self.assertContains(respuesta, "Introduzca una dirección de correo electrónico válida")

        largos = [{"nombre": "N" * 100, "correo": "", "rubro": "R" * 60} for _ in range(2)]
        respuesta = self.client.post(self.url, self.datos(socios=largos))
        self.assertContains(respuesta, "Los datos de los socios son demasiado largos")
        self.assertFalse(FilaPlanificacion.objects.filter(nrc="HOR-100").exists())
