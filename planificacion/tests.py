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
            "Activo",
        )

        self.assertIsNotNone(
            seccion.fecha_consolidacion
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="portal-as@uautonoma.cl",
    )
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
            "filas-0-horario": "Lunes 10:00 - 12:00",
            "filas-0-estudiantes_planificados": "30",
            "filas-0-posible_socio_texto": "Fundación de prueba",
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