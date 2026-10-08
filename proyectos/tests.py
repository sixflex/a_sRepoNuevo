import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academico.models import (
    Asignatura,
    Campus,
    Docente,
    PeriodoAcademico,
    Sede,
    Seccion,
    SeccionDocente,
)

from proyectos.models import (
    EnlaceRegistroEquipo,
    Equipo,
    IntegranteEquipo,
)


class RegistroEquiposCDE48Tests(TestCase):

    def setUp(self):
        self.User = get_user_model()

        
        self.grupo_estudiante, _ = Group.objects.get_or_create(
            name="Estudiante"
        )

        self.grupo_docente, _ = Group.objects.get_or_create(
            name="Docente"
        )

        
        self.sede = Sede.objects.create(
            nombre="Sede Test",
            ciudad="Santiago",
            activo=True,
        )

        self.campus = Campus.objects.create(
            sede=self.sede,
            nombre="Campus Test",
            direccion="Dirección Test",
            activo=True,
        )

        self.periodo = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="SEMESTRE",
            nombre="Periodo Test 2026",
            estado="ACTIVO",
        )

        self.asignatura = Asignatura.objects.create(
            codigo="TEST-AS",
            nombre="Asignatura Test",
            activo=True,
        )

        self.seccion = Seccion.objects.create(
            periodo=self.periodo,
            campus=self.campus,
            asignatura=self.asignatura,
            nrc="TEST-10001",
            seccion="1",
            jornada="Diurna",
            horario="Lunes 10:00",
            estado="ACTIVA",
        )

        # Segunda sección para probar aislamiento de contexto.
        self.seccion_otra = Seccion.objects.create(
            periodo=self.periodo,
            campus=self.campus,
            asignatura=self.asignatura,
            nrc="TEST-20001",
            seccion="2",
            jornada="Diurna",
            horario="Martes 10:00",
            estado="ACTIVA",
        )

        
        self.usuario_docente = self.User.objects.create_user(
            username="docente_test_cde48",
            password="TestPass123!",
            email="docente_test@cloud.uautonoma.cl",
            correo_institucional="docente_test@cloud.uautonoma.cl",
            activo=True,
        )

        self.usuario_docente.groups.add(self.grupo_docente)

        self.docente = Docente.objects.create(
            usuario=self.usuario_docente,
            rut="11111111-1",
            nombres="Docente",
            apellidos="Test",
            correo_institucional="docente_test@cloud.uautonoma.cl",
            activo=True,
        )

        SeccionDocente.objects.create(
            seccion=self.seccion,
            docente=self.docente,
            tipo_contrato="TEST",
            capacitado_as=True,
        )

        
        self.usuario_docente_ajeno = self.User.objects.create_user(
            username="docente_ajeno_cde48",
            password="TestPass123!",
            email="docente_ajeno@cloud.uautonoma.cl",
            correo_institucional="docente_ajeno@cloud.uautonoma.cl",
            activo=True,
        )

        self.usuario_docente_ajeno.groups.add(self.grupo_docente)

        self.docente_ajeno = Docente.objects.create(
            usuario=self.usuario_docente_ajeno,
            rut="22222222-2",
            nombres="Docente",
            apellidos="Ajeno",
            correo_institucional="docente_ajeno@cloud.uautonoma.cl",
            activo=True,
        )

        
        self.usuario_estudiante = self.User.objects.create_user(
            username="estudiante_test_cde48",
            password="TestPass123!",
            email="estudiante_test@cloud.uautonoma.cl",
            correo_institucional="estudiante_test@cloud.uautonoma.cl",
            first_name="Estudiante",
            last_name="Test",
            activo=True,
        )

        self.usuario_estudiante.groups.add(self.grupo_estudiante)

        
        self.enlace = EnlaceRegistroEquipo.objects.create(
            seccion=self.seccion,
            creado_por_docente=self.docente,
            fecha_inicio=timezone.now(),
            fecha_expiracion=timezone.now() + timedelta(days=7),
            activo=True,
        )

        self.url_registro = reverse(
            "proyectos:acceso_registro_equipos",
            kwargs={"token": self.enlace.token},
        )

    
    def datos_registro_validos(self, clave=None):
        if clave is None:
            clave = uuid.uuid4()

        return {
            "clave_idempotencia": str(clave),

            "tipo_socio": "provisional",
            "socio_provisional_nombre": "Organización Test",

            "cantidad_integrantes": "1",

            # RUT chileno válido de prueba
            "rut_1": "12.345.678-5",

            "nombres_1": "Estudiante",
            "apellidos_1": "Test",

            "correo_1": (
                self.usuario_estudiante.correo_institucional
            ),
        }

    
    def test_usuario_no_autenticado_retorna_al_formulario_contextual(self):
        response = self.client.get(self.url_registro)

        self.assertEqual(response.status_code, 302)

        self.assertIn(
            reverse("usuarios:login"),
            response.url,
        )

        self.assertIn(
            "next=",
            response.url,
        )

        self.assertIn(
            str(self.enlace.token),
            response.url,
        )

    
    def test_estudiante_puede_acceder_al_formulario(self):
        self.client.force_login(self.usuario_estudiante)

        response = self.client.get(self.url_registro)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["seccion"].id,
            self.seccion.id,
        )

        self.assertEqual(
            response.context["enlace"].id,
            self.enlace.id,
        )

    
    def test_docente_no_puede_registrar_equipo_como_estudiante(self):
        self.client.force_login(self.usuario_docente)

        response = self.client.get(self.url_registro)

        self.assertEqual(response.status_code, 403)

        self.assertContains(
            response,
            "solo puede ser utilizado",
            status_code=403,
        )

    
    def test_enlace_cerrado_no_permite_registro(self):
        self.enlace.activo = False
        self.enlace.save(update_fields=["activo"])

        self.client.force_login(self.usuario_estudiante)

        response = self.client.get(self.url_registro)

        self.assertEqual(response.status_code, 403)

        self.assertContains(
            response,
            "cerrado",
            status_code=403,
        )

    
    def test_enlace_expirado_no_permite_registro(self):
        self.enlace.fecha_expiracion = (
            timezone.now() - timedelta(minutes=1)
        )

        self.enlace.save(
            update_fields=["fecha_expiracion"]
        )

        self.client.force_login(self.usuario_estudiante)

        response = self.client.get(self.url_registro)

        self.assertEqual(response.status_code, 403)

        self.assertContains(
            response,
            "expirado",
            status_code=403,
        )

    
    def test_equipo_se_asocia_a_seccion_del_enlace(self):
        self.client.force_login(self.usuario_estudiante)

        datos = self.datos_registro_validos()

       
        datos["seccion_id"] = str(self.seccion_otra.id)

        response = self.client.post(
            self.url_registro,
            data=datos,
        )

        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            Equipo.objects.count(),
            1,
        )

        equipo = Equipo.objects.get()

        self.assertEqual(
            equipo.seccion_id,
            self.seccion.id,
        )

        self.assertNotEqual(
            equipo.seccion_id,
            self.seccion_otra.id,
        )

    
    def test_reenvio_misma_clave_idempotencia_no_duplica_equipo(self):
        self.client.force_login(self.usuario_estudiante)

        clave = uuid.uuid4()

        datos = self.datos_registro_validos(
            clave=clave
        )

        primera_respuesta = self.client.post(
            self.url_registro,
            data=datos,
        )

        self.assertEqual(
            primera_respuesta.status_code,
            302,
        )

        self.assertEqual(
            Equipo.objects.count(),
            1,
        )

        self.assertEqual(
            IntegranteEquipo.objects.count(),
            1,
        )

        segunda_respuesta = self.client.post(
            self.url_registro,
            data=datos,
        )

        self.assertEqual(
            segunda_respuesta.status_code,
            302,
        )

        
        self.assertEqual(
            Equipo.objects.count(),
            1,
        )

        
        self.assertEqual(
            IntegranteEquipo.objects.count(),
            1,
        )

        equipo = Equipo.objects.get()

        self.assertEqual(
            equipo.clave_idempotencia,
            clave,
        )

    
    def test_informante_no_puede_crear_dos_equipos_misma_seccion(self):
        self.client.force_login(self.usuario_estudiante)

        datos_1 = self.datos_registro_validos(
            clave=uuid.uuid4()
        )

        response_1 = self.client.post(
            self.url_registro,
            data=datos_1,
        )

        self.assertEqual(
            response_1.status_code,
            302,
        )

        self.assertEqual(
            Equipo.objects.count(),
            1,
        )

        
        datos_2 = self.datos_registro_validos(
            clave=uuid.uuid4()
        )

        response_2 = self.client.post(
            self.url_registro,
            data=datos_2,
        )

        
        self.assertEqual(
            response_2.status_code,
            200,
        )

        self.assertEqual(
            Equipo.objects.count(),
            1,
        )

        self.assertContains(
            response_2,
            "Ya registraste un equipo en esta sección",
        )

    
    def test_docente_asignado_puede_gestionar_equipos_seccion(self):
        self.client.force_login(self.usuario_docente)

        url = reverse(
            "proyectos:gestionar_equipos_seccion",
            kwargs={"seccion_id": self.seccion.id},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            200,
        )

   
    def test_docente_ajeno_no_puede_gestionar_equipos_seccion(self):
        self.client.force_login(
            self.usuario_docente_ajeno
        )

        url = reverse(
            "proyectos:gestionar_equipos_seccion",
            kwargs={"seccion_id": self.seccion.id},
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            403,
        )

   
    def test_numero_grupo_es_unico_dentro_de_seccion(self):
        Equipo.objects.create(
            seccion=self.seccion,
            numero_grupo=1,
            informante_nombre="Estudiante Uno",
            informante_correo="uno@cloud.uautonoma.cl",
            estado="Registrado",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Equipo.objects.create(
                    seccion=self.seccion,
                    numero_grupo=1,
                    informante_nombre="Estudiante Dos",
                    informante_correo="dos@cloud.uautonoma.cl",
                    estado="Registrado",
                )

    
    def test_numero_grupo_puede_repetirse_en_otra_seccion(self):
        Equipo.objects.create(
            seccion=self.seccion,
            numero_grupo=1,
            informante_nombre="Estudiante Uno",
            informante_correo="uno@cloud.uautonoma.cl",
            estado="Registrado",
        )

        Equipo.objects.create(
            seccion=self.seccion_otra,
            numero_grupo=1,
            informante_nombre="Estudiante Dos",
            informante_correo="dos@cloud.uautonoma.cl",
            estado="Registrado",
        )

        self.assertEqual(
            Equipo.objects.filter(
                numero_grupo=1
            ).count(),
            2,
        )