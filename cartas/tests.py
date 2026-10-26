from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academico.models import Asignatura, Campus, Docente, PeriodoAcademico, Seccion, Sede
from comunicaciones.models import EnvioCorreo
from socios.models import ParticipacionSocio, SocioComunitario
from cartas.models import CartaDocumento, CartaEstudiante, SolicitudCarta
from cartas.services import (
    aprobar_y_enviar_carta,
    enviar_carta_docente,
    generar_cartas_agrupadas,
    verificar_alerta_antiguedad_socio,
)

from cartas.forms import SolicitudCartaForm
from proyectos.models import Equipo, IntegranteEquipo

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


class EnvioCartaDocenteTestCase(TestCase):
    """CDE-583: envío de la carta al Docente con registro y reintento (RF-CAR-07 y RF-CAR-08)."""

    setUp_base = CartasServicesTestCase.setUp

    def setUp(self):
        self.setUp_base()
        call_command("cargar_plantillas_correo", verbosity=0)

        self.solicitud.estado = "PENDIENTE"
        self.solicitud.fecha_aprobacion = None
        self.solicitud.save()

        for orden, nombre in enumerate(["Ana Pérez", "Luis Soto"], start=1):
            CartaEstudiante.objects.create(
                solicitud=self.solicitud,
                nombre=nombre,
                rut=f"1111111{orden}-1",
                orden=orden,
            )

    def _aprobar(self):
        _, envios = aprobar_y_enviar_carta(self.solicitud.id, self.usuario)
        self.solicitud.refresh_from_db()
        return envios[0]

    def test_aprobar_genera_la_carta_y_la_envia_al_docente(self):
        envio = self._aprobar()

        self.assertEqual(self.solicitud.estado, "APROBADA")
        self.assertEqual(CartaDocumento.objects.count(), 1)
        self.assertEqual(envio.resultado, "OK")
        self.assertEqual(envio.destinatario, "docente@test.cl")
        self.assertIsNotNone(envio.fecha_envio)
        self.assertEqual(envio.carta_documento, CartaDocumento.objects.get())

        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["docente@test.cl"])
        self.assertIn("compruebe que los datos", correo.body)
        nombre, contenido, tipo = correo.attachments[0]
        self.assertEqual(tipo, "application/pdf")
        self.assertTrue(contenido.startswith(b"%PDF"))

    @patch("django.core.mail.EmailMessage.send")
    def test_envio_fallido_deja_la_carta_aprobada_y_pendiente(self, mock_send):
        mock_send.side_effect = Exception("Fallo de conexión SMTP")

        envio = self._aprobar()

        self.assertEqual(self.solicitud.estado, "APROBADA")
        self.assertEqual(envio.resultado, "ERROR")
        self.assertIn("Fallo de conexión SMTP", envio.detalle_error)
        self.assertEqual(envio.destinatario, "docente@test.cl")
        self.assertIsNone(envio.fecha_envio)

    def test_reintento_no_genera_otra_carta(self):
        with patch("django.core.mail.EmailMessage.send", side_effect=Exception("Fallo")):
            envio = self._aprobar()

        reintento = enviar_carta_docente(envio.carta_documento)

        self.assertEqual(reintento.id, envio.id)
        self.assertEqual(reintento.resultado, "OK")
        self.assertEqual(reintento.numero_intento, 2)
        self.assertEqual(CartaDocumento.objects.count(), 1)
        self.assertEqual(EnvioCorreo.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_carta_ya_enviada_no_se_vuelve_a_enviar(self):
        envio = self._aprobar()

        enviar_carta_docente(envio.carta_documento)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EnvioCorreo.objects.count(), 1)
        self.assertEqual(EnvioCorreo.objects.get().numero_intento, 1)

    def test_aprobar_dos_veces_no_genera_otra_carta(self):
        self._aprobar()

        with self.assertRaises(ValueError):
            aprobar_y_enviar_carta(self.solicitud.id, self.usuario)

        self.assertEqual(CartaDocumento.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_boton_reintentar_reenvia_la_misma_carta(self):
        self.usuario.groups.add(Group.objects.get_or_create(name="Coordinador")[0])
        self.client.force_login(self.usuario)

        with patch("django.core.mail.EmailMessage.send", side_effect=Exception("Fallo")):
            envio = self._aprobar()

        detalle = reverse("cartas:detalle_solicitud_coordinacion", args=[self.solicitud.id])
        self.assertContains(self.client.get(detalle), "Reintentar envío")

        respuesta = self.client.post(
            reverse("cartas:reintentar_envio_carta", args=[envio.carta_documento_id])
        )

        self.assertRedirects(respuesta, detalle)
        envio.refresh_from_db()
        self.assertEqual(envio.resultado, "OK")
        self.assertEqual(CartaDocumento.objects.count(), 1)
        self.assertNotContains(self.client.get(detalle), "Reintentar envío")

class SolicitudCartaFormTestCase(TestCase):

    def setUp(self):
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
        
        self.equipo = Equipo.objects.create(
            seccion=self.seccion, numero_grupo=1, estado="ACTIVO"
        )

        self.datos_formulario = {
            "institucion_receptora": "Fundación Test",
            "persona_receptora": "Director Test",
            "cargo_receptor": "Director",
            "consideraciones": "Sin consideraciones.",
            "equipo": self.equipo.id,
        }

    def test_formulario_invalido_con_siete_integrantes(self):
        for i in range(7):
            IntegranteEquipo.objects.create(
                equipo=self.equipo,
                rut=f"1111111{i}-1",
                nombres=f"Estudiante {i}",
                apellidos="Test",
                correo_institucional=f"est{i}@test.cl"
            )

        form = SolicitudCartaForm(data=self.datos_formulario)
        
        self.assertFalse(form.is_valid())
        self.assertIn("equipo", form.errors)
        
        self.assertTrue(
            any("máximo de 6 estudiantes" in error for error in form.errors["equipo"])
        )

    def test_formulario_valido_con_seis_integrantes(self):
        for i in range(6):
            IntegranteEquipo.objects.create(
                equipo=self.equipo,
                rut=f"1111111{i}-1",
                nombres=f"Estudiante {i}",
                apellidos="Test",
                correo_institucional=f"est{i}@test.cl"
            )

        form = SolicitudCartaForm(data=self.datos_formulario)
        
        self.assertTrue(form.is_valid())