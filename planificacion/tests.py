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
from planificacion.forms import DocenteFilaForm, FilaPlanificacionForm, opciones_planificacion
from planificacion.models import (FilaPlanificacion,FilaPlanificacionDocente,Planificacion,PlanificacionEnlace,PlanificacionError,)
from planificacion.services import (
    PlanificacionNoAprobable,
    aprobar_planificacion,
    asignaturas_parecidas,
    devolver_planificacion,
    revisar_planificacion,
    separar_nombre,
)


def validar_y_consolidar_planificacion(planificacion):
    """Envío final de Dirección + «Aprobar planificación» del Coordinador (HU-01)."""
    planificacion.estado = "FINAL"
    planificacion.save(update_fields=["estado"])
    try:
        aprobar_planificacion(planificacion)
    except PlanificacionNoAprobable:
        pass
    planificacion.refresh_from_db()


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
        # Oferta académica: la carrera se imparte en el campus del enlace.
        self.carrera.campus.add(self.campus)

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
            rut="12345678-5",
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

    def _fila_con_docente(self, nrc="77777", **docente):
        fila = FilaPlanificacion.objects.create(
            planificacion=self.planificacion,
            numero_fila=1,
            facultad_texto=self.facultad.nombre,
            carrera_texto=self.carrera.nombre,
            declaracion_as=True,
            nrc=nrc,
            campus_texto=self.campus.nombre,
            seccion="1",
            asignatura_texto=self.asignatura.nombre,
            nivel="5",
            jornada="Diurna",
            estudiantes_planificados=20,
            estado_validacion="PENDIENTE",
        )
        FilaPlanificacionDocente.objects.create(fila=fila, **docente)
        return fila

    def test_docente_nuevo_sin_datos_para_registrarlo_queda_observado(self):
        fila = self._fila_con_docente(nombre="Docente inexistente", correo="noexiste@uautonoma.cl")

        validar_y_consolidar_planificacion(self.planificacion)

        fila.refresh_from_db()
        self.assertEqual(fila.estado_validacion, "OBSERVADA")
        self.assertIsNone(fila.seccion_resultante)
        self.assertEqual(self.planificacion.estado, "FINAL")
        self.assertEqual(self.planificacion.filas_observadas, 1)
        error = PlanificacionError.objects.get(fila=fila, codigo="DOCENTE_NUEVO_INCOMPLETO")
        self.assertIn("falta el RUT", error.mensaje)

    def test_docente_nuevo_se_registra_al_aprobar(self):
        fila = self._fila_con_docente(
            rut="13552773-4", nombre="Juan Valdez", correo="juan.valdez@uautonoma.cl", telefono="987654321",
        )

        validar_y_consolidar_planificacion(self.planificacion)

        fila.refresh_from_db()
        self.assertEqual(fila.estado_validacion, "ACEPTADA")
        docente = Docente.objects.get(rut="13552773-4")
        self.assertEqual((docente.nombres, docente.apellidos), ("Juan", "Valdez"))
        self.assertEqual(docente.correo_institucional, "juan.valdez@uautonoma.cl")
        self.assertTrue(SeccionDocente.objects.filter(seccion=fila.seccion_resultante, docente=docente).exists())
        self.assertEqual(self.planificacion.estado, "APROBADA")

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

        # La facultad la fija el enlace; la carrera se elige entre las suyas.
        self.assertContains(response, '<span class="plan-facultad-fija" title="Definida por el enlace">Facultad de Ingeniería</span>')
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
            "filas-0-horario_4": "18:30",
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

        # El envío final queda por revisar: todavía no se crea nada.
        self.assertEqual(self.planificacion.estado, "FINAL")
        self.assertIsNotNone(self.planificacion.fecha_envio_final)
        self.assertEqual(self.planificacion.filas_recibidas, 1)
        self.assertEqual(self.planificacion.filas_aceptadas, 0)
        self.assertEqual(self.planificacion.filas_observadas, 0)
        fila = self.planificacion.filas.get(numero_fila=1)
        self.assertEqual(fila.estado_validacion, "PENDIENTE")
        self.assertIsNone(fila.seccion_resultante)
        self.assertFalse(Seccion.objects.filter(nrc="HU01-100").exists())
        self.assertTrue(
            AuditoriaCambio.objects.filter(
                entidad="Planificacion",
                entidad_id=str(self.planificacion.id),
                accion="ENVIO_FINAL_PLANIFICACION",
            ).exists()
        )

        # Enviada, Dirección ya no puede volver a enviarla.
        self.client.post(url, data=datos)
        self.assertEqual(self.planificacion.filas.count(), 1)

        # El Coordinador aprueba: recién ahí se crea la sección.
        coordinador = get_user_model().objects.create_superuser("coord_hu01", "coord@uautonoma.cl", "Prueba1234")
        self.client.force_login(coordinador)
        self.client.post(reverse("core:aprobar_planificacion_coordinacion", args=[self.planificacion.id]))

        self.planificacion.refresh_from_db()
        fila.refresh_from_db()
        self.assertEqual(self.planificacion.estado, "APROBADA")
        self.assertEqual(self.planificacion.filas_aceptadas, 1)
        self.assertEqual(fila.estado_validacion, "ACEPTADA")
        self.assertEqual(fila.horario, "Lunes 10:00, Jueves 18:30")
        self.assertEqual(fila.seccion_resultante.horario, "Lunes 10:00, Jueves 18:30")
        self.assertEqual(fila.posible_socio_texto, "Fundación de prueba")
        self.assertEqual(Seccion.objects.filter(periodo=self.periodo, nrc="HU01-100").count(), 1)
        self.assertTrue(
            AuditoriaCambio.objects.filter(
                entidad="Planificacion", entidad_id=str(self.planificacion.id), accion="APROBAR_PLANIFICACION",
            ).exists()
        )

        # Aprobar dos veces no duplica nada.
        self.client.post(reverse("core:aprobar_planificacion_coordinacion", args=[self.planificacion.id]))
        self.assertEqual(Seccion.objects.filter(periodo=self.periodo, nrc="HU01-100").count(), 1)


class HorarioYSociosPlanificacionTestCase(TestCase):
    """Subtareas 2.1 y 2.2: horario por días y socios opcionales en la planilla de Dirección."""

    setUp_base = PlanificacionHU01TestCase.setUp

    def setUp(self):
        self.setUp_base()
        self.url = reverse("planificacion:formulario_tabular_as", kwargs={"token": self.enlace.token})

    def datos(self, boton="guardar_borrador", dias=("Lu", "Mi"), hora="08:30", socios=(), horas=None):
        """`hora` va en todos los días marcados; `horas` = {'Ma': '17:00'} da una hora por día."""
        codigos = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá"]
        horas = horas if horas is not None else {dia: hora for dia in dias}
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
            **{f"filas-0-horario_{i}": horas.get(codigo, "") for i, codigo in enumerate(codigos, start=1)},
            "filas-0-horario_7": "",
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

        self.assertEqual(
            texto_horario({"Ju": time(20, 0), "Ma": time(17, 0)}),
            "Martes 17:00, Jueves 20:00",
        )
        self.assertEqual(leer_horario("Martes 17:00, Jueves 20:00"), {"Ma": "17:00", "Ju": "20:00"})
        # Formato anterior (una hora para todos los días) se sigue leyendo.
        self.assertEqual(leer_horario("Lunes, Miércoles 08:30"), {"Lu": "08:30", "Mi": "08:30"})
        self.assertEqual(leer_horario("Lu, Mi 08:30"), {"Lu": "08:30", "Mi": "08:30"})
        self.assertIsNone(leer_horario("Lunes 10:00 - 12:00"))
        self.assertIsNone(leer_horario("Lunes, Martes"))
        self.assertEqual(
            texto_socios([{"nombre": "Junta | Norte", "correo": "", "rubro": "Barrio"}, {"nombre": "", "correo": "", "rubro": ""}]),
            "Junta / Norte |  | Barrio",
        )
        self.assertEqual(
            leer_socios("Fundación antigua"),
            [{"nombre": "Fundación antigua", "correo": "", "rubro": "", "direccion": ""}],
        )
        # Las líneas guardadas antes de la dirección se siguen leyendo.
        self.assertEqual(leer_socios("Almacén | a@b.cl | Comercio")[0]["direccion"], "")
        self.assertEqual(
            texto_socios([{"nombre": "Almacén", "correo": "", "rubro": "Comercio", "direccion": "Av. Siempre Viva 742"}]),
            "Almacén |  | Comercio | Av. Siempre Viva 742",
        )
        self.assertEqual(leer_socios("Por definir"), [])

    def test_marcar_dias_y_hora_guarda_el_texto_y_el_borrador_lo_vuelve_a_marcar(self):
        self.client.post(self.url, self.datos())

        self.assertEqual(self.fila().horario, "Lunes 08:30, Miércoles 08:30")
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

        self.assertContains(respuesta, "Ingrese la hora de inicio de: Lunes, Miércoles.")

    def test_cada_dia_puede_tener_su_hora(self):
        self.client.post(self.url, self.datos(dias=("Ma", "Ju"), horas={"Ma": "17:00", "Ju": "20:00"}))
        self.assertEqual(self.fila().horario, "Martes 17:00, Jueves 20:00")

        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'name="filas-0-horario_2" value="17:00"')
        self.assertContains(respuesta, 'name="filas-0-horario_4" value="20:00"')

    def test_solo_un_dia_sin_hora_lo_nombra(self):
        respuesta = self.client.post(self.url, self.datos(dias=("Ma", "Ju"), horas={"Ma": "17:00"}))
        self.assertContains(respuesta, "Ingrese la hora de inicio de: Jueves.")

    def test_hora_de_dia_desmarcado_no_se_guarda(self):
        self.client.post(self.url, self.datos(dias=("Ma",), horas={"Ma": "17:00", "Vi": "09:00"}))
        self.assertEqual(self.fila().horario, "Martes 17:00")

    def test_horario_antiguo_se_muestra_y_no_se_pierde(self):
        form = FilaPlanificacionForm(instance=FilaPlanificacion(horario="Lunes 10:00 - 12:00"))
        html = str(form["horario"])

        self.assertIn("Guardado: Lunes 10:00 - 12:00", html)
        self.assertIn('value="Lunes 10:00 - 12:00"', html)

        datos = self.datos(dias=(), hora="")
        datos["filas-0-horario_7"] = "Lunes 10:00 - 12:00"
        self.client.post(self.url, datos)
        self.assertEqual(self.fila().horario, "Lunes 10:00 - 12:00")

    def test_aprobar_lleva_el_horario_a_la_seccion(self):
        self.client.post(self.url, self.datos(boton="enviar_final", dias=("Ma", "Ju"), horas={"Ma": "17:00", "Ju": "20:00"}))
        self.planificacion.refresh_from_db()
        aprobar_planificacion(self.planificacion)

        self.assertEqual(self.fila().seccion_resultante.horario, "Martes 17:00, Jueves 20:00")

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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RevisionCoordinadorPlanificacionTestCase(TestCase):
    """
    Dirección informa asignaturas y docentes; el Coordinador revisa, corrige
    filas, aprueba (se crea lo nuevo) o devuelve con un motivo por correo.
    """

    setUp_base = PlanificacionHU01TestCase.setUp
    crear_fila_valida = PlanificacionHU01TestCase.crear_fila_valida

    def setUp(self):
        self.setUp_base()
        self.planificacion.estado = "FINAL"
        self.planificacion.save()
        self.coordinador = get_user_model().objects.create_superuser("coord_rev", "coord.rev@uautonoma.cl", "Prueba1234")
        self.client.force_login(self.coordinador)
        self.url_detalle = reverse("core:detalle_planificacion_coordinacion", args=[self.planificacion.id])

    def fila_con_asignatura(self, nombre):
        fila = self.crear_fila_valida()
        fila.asignatura_texto = nombre
        fila.save()
        return fila

    def test_asignatura_nueva_no_es_observacion_y_se_crea_al_aprobar(self):
        fila = self.fila_con_asignatura("Consultoría de Empresas")

        revisar_planificacion(self.planificacion)
        fila.refresh_from_db()
        self.assertEqual(fila.estado_validacion, "PENDIENTE")
        self.assertFalse(fila.errores.exists())
        self.assertContains(self.client.get(self.url_detalle), "Nueva")

        aprobar_planificacion(self.planificacion)
        nueva = Asignatura.objects.get(nombre="Consultoría de Empresas")
        self.assertIsNone(nueva.codigo)
        self.assertIn(self.carrera, nueva.carreras.all())
        fila.refresh_from_db()
        self.assertEqual(fila.seccion_resultante.asignatura, nueva)

    def test_asignatura_se_reconoce_sin_tildes_ni_mayusculas(self):
        self.asignatura.nombre = "Consultoría de Empresas"
        self.asignatura.save()
        self.fila_con_asignatura("consultoria de empresas")

        aprobar_planificacion(self.planificacion)

        self.assertEqual(Asignatura.objects.filter(nombre__icontains="consult").count(), 1)

    def test_asignatura_de_otra_carrera_se_asocia_sin_duplicarla(self):
        otra = Carrera.objects.create(facultad=self.facultad, codigo="IND-HU01", nombre="Ingeniería Industrial", activo=True)
        self.asignatura.carreras.set([otra])
        self.crear_fila_valida()

        aprobar_planificacion(self.planificacion)

        self.assertEqual(Asignatura.objects.filter(nombre=self.asignatura.nombre).count(), 1)
        self.assertEqual(set(self.asignatura.carreras.all()), {otra, self.carrera})

    def test_avisa_asignaturas_parecidas(self):
        self.asignatura.nombre = "Consultoría de Empresas"
        self.asignatura.save()

        parecidas = asignaturas_parecidas("Consultoria", self.carrera)

        self.assertEqual(parecidas, [self.asignatura])
        self.fila_con_asignatura("Consultoria")
        revisar_planificacion(self.planificacion)
        self.assertContains(self.client.get(self.url_detalle), "¿Será «Consultoría de Empresas»?")

    def test_no_se_aprueba_con_filas_observadas(self):
        fila = self.crear_fila_valida()
        fila.docentes.update(rut=None, correo=None)

        respuesta = self.client.post(
            reverse("core:aprobar_planificacion_coordinacion", args=[self.planificacion.id]), follow=True,
        )

        self.assertContains(respuesta, "fila(s) observada(s)")
        self.planificacion.refresh_from_db()
        self.assertEqual(self.planificacion.estado, "FINAL")
        self.assertEqual(self.planificacion.filas_observadas, 1)
        self.assertFalse(Seccion.objects.filter(nrc="12345").exists())

    def test_coordinador_corrige_la_fila_y_queda_lista(self):
        fila = self.crear_fila_valida()
        fila.docentes.update(rut=None, correo=None)
        revisar_planificacion(self.planificacion)
        url = reverse("core:editar_fila_planificacion_coordinacion", args=[self.planificacion.id, fila.id])
        self.assertContains(self.client.get(url), "Guardar fila")
        docente_fila = fila.docentes.get()

        self.client.post(url, {
            "facultad_texto": self.facultad.nombre,
            "carrera_texto": self.carrera.nombre,
            "declaracion_as": "on",
            "nrc": "12345",
            "seccion": "1",
            "asignatura_texto": self.asignatura.nombre,
            "nivel": "5",
            "jornada": "Diurna",
            "horario_0": ["Ma", "Ju"],
            "horario_2": "17:00",
            "horario_4": "20:00",
            "estudiantes_planificados": "25",
            "docentes-TOTAL_FORMS": "1",
            "docentes-INITIAL_FORMS": "0",
            "docentes-0-id": str(docente_fila.id),
            "docentes-0-rut": "13552773-4",
            "docentes-0-nombre": "Juan Valdez",
            "docentes-0-correo": "juan.valdez@uautonoma.cl",
        })

        fila.refresh_from_db()
        self.assertEqual(fila.estado_validacion, "PENDIENTE")
        self.assertEqual(fila.horario, "Martes 17:00, Jueves 20:00")
        self.assertEqual(fila.docentes.get().rut, "13552773-4")
        self.assertTrue(AuditoriaCambio.objects.filter(accion="EDITAR_FILA_PLANIFICACION", entidad_id=str(fila.id)).exists())

    def test_devolver_avisa_por_correo_y_reabre_el_enlace(self):
        self.crear_fila_valida()
        self.enlace.fecha_expiracion = timezone.now() - timedelta(days=1)
        self.enlace.save()

        self.client.post(
            reverse("core:devolver_planificacion_coordinacion", args=[self.planificacion.id]),
            {"motivo": "Falta el NRC de Consultoría de Empresas."},
        )

        self.planificacion.refresh_from_db()
        self.enlace.refresh_from_db()
        self.assertEqual(self.planificacion.estado, "DEVUELTA")
        self.assertGreater(self.enlace.fecha_expiracion, timezone.now() + timedelta(days=6))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Falta el NRC de Consultoría de Empresas.", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.enlace.destinatario_correo])

        self.client.logout()
        url_enlace = reverse("planificacion:formulario_tabular_as", kwargs={"token": self.enlace.token})
        respuesta = self.client.get(url_enlace)
        self.assertContains(respuesta, "devolvió la planificación")
        self.assertContains(respuesta, "Falta el NRC de Consultoría de Empresas.")
        self.assertContains(respuesta, "Enviar versión final")

    def test_devolver_exige_motivo(self):
        self.client.post(reverse("core:devolver_planificacion_coordinacion", args=[self.planificacion.id]), {"motivo": " "})

        self.planificacion.refresh_from_db()
        self.assertEqual(self.planificacion.estado, "FINAL")
        self.assertEqual(len(mail.outbox), 0)

    def test_separar_nombre(self):
        self.assertEqual(separar_nombre("Juan Valdez"), ("Juan", "Valdez"))
        self.assertEqual(separar_nombre("Juan Pérez Soto"), ("Juan", "Pérez Soto"))
        self.assertEqual(separar_nombre("María José Pérez Soto"), ("María José", "Pérez Soto"))
        self.assertEqual(separar_nombre("Juan"), ("Juan", ""))

    def test_rut_invalido_en_el_enlace_avisa_al_tiro(self):
        form = DocenteFilaForm(data={"rut": "12345678-9", "nombre": "Juan Valdez"})
        self.assertFalse(form.is_valid())
        self.assertIn("rut", form.errors)
        form = DocenteFilaForm(data={"rut": "13.552.773-4", "nombre": "Juan Valdez"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["rut"], "13552773-4")


class FacultadFijaEnlaceTestCase(TestCase):
    """La unidad del enlace fija la facultad; la carrera se elige solo entre las de esa facultad."""

    setUp_base = PlanificacionHU01TestCase.setUp
    crear_fila_valida = PlanificacionHU01TestCase.crear_fila_valida

    def setUp(self):
        self.setUp_base()
        self.otra_facultad = Facultad.objects.create(codigo="FADER", nombre="Facultad de Derecho", activo=True)
        self.derecho = Carrera.objects.create(facultad=self.otra_facultad, codigo="DER", nombre="Derecho", activo=True)
        self.industrial = Carrera.objects.create(facultad=self.facultad, codigo="IND", nombre="Ingeniería Industrial", activo=True)
        self.industrial.campus.add(self.campus)
        self.url = reverse("planificacion:formulario_tabular_as", kwargs={"token": self.enlace.token})

    def test_solo_ofrece_las_carreras_de_la_facultad(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, '<option value="Ingeniería Industrial"')
        self.assertNotContains(respuesta, '<option value="Derecho"')
        self.assertNotContains(respuesta, 'name="filas-0-facultad_texto" class="form-select')

    def test_la_facultad_no_se_puede_cambiar_desde_el_formulario(self):
        form = FilaPlanificacionForm(
            data={"facultad_texto": "Facultad de Derecho", "carrera_texto": "Ingeniería Industrial", "nrc": "1", "seccion": "1", "asignatura_texto": "X"},
            opciones=opciones_planificacion(self.facultad),
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["facultad_texto"], "Facultad de Ingeniería")

    def test_carrera_de_otra_facultad_queda_observada(self):
        fila = self.crear_fila_valida()
        fila.carrera_texto = "Derecho"
        fila.save()

        revisar_planificacion(self.planificacion)

        fila.refresh_from_db()
        self.assertEqual(fila.estado_validacion, "OBSERVADA")
        self.assertTrue(fila.errores.filter(codigo="CARRERA_FUERA_DE_FACULTAD").exists())


class CarreraPorCampusPlanificacionTestCase(TestCase):
    """CarreraCampus: la planilla de un enlace solo ofrece las carreras impartidas en su campus."""

    setUp_base = PlanificacionHU01TestCase.setUp
    crear_fila_valida = PlanificacionHU01TestCase.crear_fila_valida

    def setUp(self):
        self.setUp_base()
        self.el_llano = Campus.objects.create(sede=self.sede, nombre="Campus El Llano", activo=True)
        self.industrial = Carrera.objects.create(facultad=self.facultad, codigo="IND", nombre="Ingeniería Industrial", activo=True)
        self.industrial.campus.add(self.el_llano)

    def test_planilla_de_el_llano_solo_ofrece_sus_carreras(self):
        # Unidad de facultad: la planilla no trae una carrera precargada.
        self.unidad.carrera = None
        self.unidad.save()
        enlace = PlanificacionEnlace.objects.create(
            unidad_academica=self.unidad, campus=self.el_llano, periodo=self.periodo,
            destinatario_nombre="Dirección", destinatario_correo="direccion@uautonoma.cl",
            fecha_emision=timezone.now(), fecha_expiracion=timezone.now() + timedelta(days=5), activo=True,
        )

        respuesta = self.client.get(reverse("planificacion:formulario_tabular_as", kwargs={"token": enlace.token}))

        self.assertContains(respuesta, '<option value="Ingeniería Industrial"')
        self.assertNotContains(respuesta, '<option value="Ingeniería Civil Informática"')

    def test_carrera_no_impartida_en_el_campus_queda_observada(self):
        fila = self.crear_fila_valida()
        fila.carrera_texto = "Ingeniería Industrial"
        fila.save()

        revisar_planificacion(self.planificacion)

        fila.refresh_from_db()
        self.assertEqual(fila.estado_validacion, "OBSERVADA")
        self.assertTrue(fila.errores.filter(codigo="CARRERA_NO_IMPARTIDA_EN_CAMPUS").exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EnlacesVariasUnidadesTestCase(TestCase):
    """Generar enlaces marcando varias unidades: uno individual por unidad, con su correo."""

    setUp_base = PlanificacionHU01TestCase.setUp

    def setUp(self):
        self.setUp_base()
        # Derecho se imparte en Providencia y El Llano; Informática solo en Providencia.
        self.el_llano = Campus.objects.create(sede=self.sede, nombre="Campus El Llano", activo=True)
        facultad_derecho = Facultad.objects.create(codigo="FADER", nombre="Facultad de Derecho", activo=True)
        self.carrera_derecho = Carrera.objects.create(facultad=facultad_derecho, nombre="Derecho", activo=True)
        self.carrera_derecho.campus.add(self.campus, self.el_llano)
        self.derecho = UnidadAcademica.objects.create(
            facultad=facultad_derecho, tipo="Dirección de Carrera", nombre="Dirección de Derecho",
            correo_oficial="derecho@uautonoma.cl", activo=True,
        )
        coordinador = get_user_model().objects.create_superuser("coord_env", "coord.env@uautonoma.cl", "Prueba1234")
        self.client.force_login(coordinador)
        self.url = reverse("proyectos:gestionar_enlaces")
        self.fecha = (timezone.localdate() + timedelta(days=10)).isoformat()

    def datos(self, **extra):
        return {
            "accion": "crear",
            "unidades": [str(self.unidad.id), str(self.derecho.id)],
            f"nombre_{self.unidad.id}": "Dirección ICI",
            f"correo_{self.unidad.id}": "otra.persona@uautonoma.cl",
            f"nombre_{self.derecho.id}": "Dirección de Derecho",
            f"correo_{self.derecho.id}": "derecho@uautonoma.cl",
            "campus": [str(self.campus.id)],
            "periodo": str(self.periodo.id),
            "fecha_expiracion": self.fecha,
            **extra,
        }

    def test_crea_un_enlace_y_un_correo_por_unidad(self):
        antes = PlanificacionEnlace.objects.count()

        self.client.post(self.url, self.datos())

        self.assertEqual(PlanificacionEnlace.objects.count(), antes + 2)
        enlace = PlanificacionEnlace.objects.get(unidad_academica=self.unidad, destinatario_correo="otra.persona@uautonoma.cl")
        self.assertEqual(enlace.destinatario_nombre, "Dirección ICI")
        self.assertTrue(PlanificacionEnlace.objects.filter(unidad_academica=self.derecho).exists())
        self.assertEqual(sorted(correo.to[0] for correo in mail.outbox), ["derecho@uautonoma.cl", "otra.persona@uautonoma.cl"])
        self.assertEqual(AuditoriaCambio.objects.filter(accion="CREAR_ENLACE").count(), 2)

    def test_si_una_unidad_esta_mal_no_crea_ninguno(self):
        antes = PlanificacionEnlace.objects.count()

        respuesta = self.client.post(self.url, self.datos(**{f"correo_{self.derecho.id}": ""}), follow=True)

        self.assertContains(respuesta, "Dirección de Derecho: falta el nombre o el correo")
        self.assertEqual(PlanificacionEnlace.objects.count(), antes)
        self.assertEqual(len(mail.outbox), 0)

    def test_un_enlace_por_cada_campus_donde_se_imparte(self):
        self.client.post(self.url, self.datos(campus=[str(self.campus.id), str(self.el_llano.id)]))

        self.assertEqual(
            set(PlanificacionEnlace.objects.filter(unidad_academica=self.derecho).values_list("campus__nombre", flat=True)),
            {"Campus Providencia", "Campus El Llano"},
        )
        # Informática solo se imparte en Providencia: no recibe enlace de El Llano.
        self.assertFalse(PlanificacionEnlace.objects.filter(unidad_academica=self.unidad, campus=self.el_llano).exists())
        self.assertEqual(len(mail.outbox), 3)

    def test_unidad_que_no_se_imparte_en_el_campus_se_avisa(self):
        antes = PlanificacionEnlace.objects.filter(unidad_academica=self.unidad).count()

        respuesta = self.client.post(self.url, self.datos(campus=[str(self.el_llano.id)]), follow=True)

        self.assertEqual(PlanificacionEnlace.objects.filter(unidad_academica=self.derecho, campus=self.el_llano).count(), 1)
        self.assertEqual(PlanificacionEnlace.objects.filter(unidad_academica=self.unidad).count(), antes)
        self.assertContains(respuesta, "No se envió enlace a Ingeniería Civil Informática")
        self.assertEqual(len(mail.outbox), 1)

    def test_unidad_sin_campus_configurado_no_crea_ninguno(self):
        self.carrera_derecho.campus.clear()
        antes = PlanificacionEnlace.objects.count()

        respuesta = self.client.post(self.url, self.datos(), follow=True)

        self.assertContains(respuesta, "Dirección de Derecho: su carrera no tiene campus registrados")
        self.assertEqual(PlanificacionEnlace.objects.count(), antes)
        self.assertEqual(len(mail.outbox), 0)

    def test_sin_campus_marcado_avisa(self):
        respuesta = self.client.post(self.url, self.datos(campus=[]), follow=True)
        self.assertContains(respuesta, "Marque al menos un campus.")

    def test_modal_muestra_donde_se_imparte_cada_unidad(self):
        respuesta = self.client.get(self.url)

        self.assertContains(respuesta, 'name="campus" value="%s"' % self.el_llano.id)
        self.assertContains(respuesta, f'data-campus-unidad="{self.campus.id}"')
        self.assertContains(respuesta, "Campus El Llano")

    def test_sin_unidades_marcadas_avisa(self):
        respuesta = self.client.post(self.url, self.datos(unidades=[]), follow=True)
        self.assertContains(respuesta, "Marque al menos una unidad académica.")

    def test_el_modal_trae_el_correo_oficial(self):
        respuesta = self.client.get(self.url)
        self.assertContains(respuesta, 'value="derecho@uautonoma.cl"')
        self.assertContains(respuesta, 'name="unidades" value="%s"' % self.derecho.id)
