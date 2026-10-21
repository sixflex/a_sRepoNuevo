from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from academico.models import Asignatura, Campus, Docente, PeriodoAcademico, Seccion, Sede
from socios.models import ParticipacionSocio, SocioComunitario
from cartas.models import CartaEstudiante, SolicitudCarta
from cartas.services import (
    generar_cartas_agrupadas,
    verificar_alerta_antiguedad_socio,
)

User = get_user_model()


class CartasServicesTestCase(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="coordinador1",
            first_name="Coordinador",
            last_name="Test",
            email="coordinador@test.cl",
            password="password123",
        )

        self.docente = Docente.objects.create(
            rut="11111111-1",
            nombres="Docente",
            apellidos="Test",
            correo_institucional="docente@test.cl",
            activo=True,
        )

        self.socio = SocioComunitario.objects.create(
            nombre_organizacion="Fundación Test",
            rut="12345678-9",
            estado_revision="APROBADO",
            es_provisional=False,
            activo=True,
            fecha_creacion=timezone.now(),
        )

        self.sede = Sede.objects.create(nombre="Santiago", activo=True)
        self.campus = Campus.objects.create(
            nombre="Campus Central", sede=self.sede, activo=True
        )
        self.periodo = PeriodoAcademico.objects.create(
            nombre="2026-10", anio=2026
        )
        self.asignatura = Asignatura.objects.create(
            nombre="Taller A+S", codigo="TAS101", activo=True
        )

        self.seccion = Seccion.objects.create(
            nrc="12345",
            seccion="1",
            asignatura=self.asignatura,
            campus=self.campus,
            periodo=self.periodo,
            estado="ACTIVA",
        )

        ahora = timezone.now()
        self.solicitud = SolicitudCarta.objects.create(
            socio=self.socio,
            seccion=self.seccion,
            campus=self.campus,
            sede=self.sede,
            solicitante_usuario=self.usuario,
            docente_derivador=self.docente,
            solicitante_tipo="DOCENTE",
            solicitante_nombre="Coordinador Test",
            solicitante_correo="coordinador@test.cl",
            estado="APROBADA",
            persona_receptora="Director Test",
            institucion_receptora="Fundación Test",
            fecha_solicitud=ahora,
            fecha_aprobacion=ahora,
        )

    def test_agrupacion_mas_de_seis_estudiantes(self):
        for i in range(10):
            CartaEstudiante.objects.create(
                solicitud=self.solicitud,
                nombre=f"Estudiante {i}",
                rut=f"1234567{i}-K",
                orden=i,
            )

        resultado = generar_cartas_agrupadas(self.solicitud, self.usuario)

        self.assertEqual(resultado["total_cartas"], 2)
        self.assertEqual(len(resultado["cartas"]), 2)

    def test_alerta_antiguedad_socio(self):
        self.assertTrue(verificar_alerta_antiguedad_socio(self.socio))

        ParticipacionSocio.objects.create(
            socio=self.socio,
            fecha_inicio=timezone.now().date() - timedelta(days=30),
        )
        self.assertFalse(verificar_alerta_antiguedad_socio(self.socio))