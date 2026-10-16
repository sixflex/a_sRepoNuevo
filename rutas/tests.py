from django.test import TestCase

from academico.models import (Asignatura,Campus,Carrera,Facultad,PeriodoAcademico,Seccion,SeccionCarrera,Sede)
from rutas.models import (RutaActividad,RutaPlantilla,RutaVersion,SeccionActividad,SeccionRuta,)
from rutas.services import asignar_ruta_as_si_corresponde
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from academico.models import Docente, SeccionDocente
from rutas.views import recalcular_avance
import os
import uuid
from unittest.mock import patch
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from encuestas import services as encuestas_services
from encuestas.models import EnlaceFormulario
from rutas.services import url_recurso
from django.test import TestCase
from auditoria.models import AuditoriaCambio

from .models import RutaActividad, RutaPlantilla, RutaVersion
from .services import crear_nueva_version_ruta
from django.core.exceptions import ValidationError

class RutaDocenteTestCase(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre="Sede Santiago",activo=True,)

        self.campus = Campus.objects.create(sede=self.sede,nombre="Campus Providencia",activo=True,)

        self.facultad = Facultad.objects.create(nombre="Facultad de Ingeniería",activo=True,)

        self.carrera = Carrera.objects.create(facultad=self.facultad,nombre="Ingeniería Civil Informática",activo=True,)

        self.asignatura = Asignatura.objects.create(codigo="AS001",nombre="Asignatura A+S",activo=True,)

        self.asignatura.carreras.add(self.carrera)

        self.periodo = PeriodoAcademico.objects.create(anio=2026,tipo="Segundo semestre",nombre="Primavera 2026",estado="Activo",)

        self.plantilla = RutaPlantilla.objects.create(nombre="Ruta del Docente A+S",descripcion="Ruta 2026",activo=True,)

        self.version = RutaVersion.objects.create(plantilla=self.plantilla,numero_version=1,estado="BORRADOR",)

        for orden in range(1, 24):
            RutaActividad.objects.create(ruta_version=self.version,etapa="Etapa de prueba",nombre=f"Actividad {orden}",es_obligatoria=True,orden=orden,)

        self.version.estado = "ACTIVA"
        self.version.save(update_fields=["estado"])

    def crear_seccion(self, nrc, declaracion_as=True):
        seccion = Seccion.objects.create(
            periodo=self.periodo,
            campus=self.campus,
            asignatura=self.asignatura,
            nrc=nrc,
            seccion="1",
            estado="Activo",
        )

        SeccionCarrera.objects.create(
            seccion=seccion,
            carrera=self.carrera,
            declaracion_as=declaracion_as,
        )

        return seccion

    def test_seccion_as_recibe_ruta(self):
        seccion = self.crear_seccion("RUTA001")

        ruta = asignar_ruta_as_si_corresponde(seccion)

        self.assertIsNotNone(ruta)
        self.assertEqual(ruta.seccion, seccion)
        self.assertEqual(ruta.ruta_version, self.version)
        self.assertEqual(ruta.estado, "EN_PROGRESO")
        self.assertEqual(ruta.porcentaje_final, 0)

    def test_seccion_as_recibe_23_actividades(self):
        seccion = self.crear_seccion("RUTA002")

        ruta = asignar_ruta_as_si_corresponde(seccion)

        total = SeccionActividad.objects.filter(seccion_ruta=ruta).count()

        self.assertEqual(total, 23)

    def test_reasignar_ruta_no_duplica_actividades(self):
        seccion = self.crear_seccion("RUTA003")

        asignar_ruta_as_si_corresponde(seccion)
        asignar_ruta_as_si_corresponde(seccion)

        ruta = SeccionRuta.objects.get(seccion=seccion)

        total = SeccionActividad.objects.filter(seccion_ruta=ruta).count()

        self.assertEqual(total, 23)
        self.assertEqual(SeccionRuta.objects.filter(seccion=seccion).count(),1,)

    def test_seccion_no_as_no_recibe_ruta(self):
        seccion = self.crear_seccion(
            "RUTA004",
            declaracion_as=False,
        )

        resultado = asignar_ruta_as_si_corresponde(seccion)

        self.assertIsNone(resultado)
        self.assertFalse(SeccionRuta.objects.filter(seccion=seccion).exists())

    def test_sin_version_activa_no_asigna_ruta(self):
        self.version.estado = "INACTIVA"
        self.version.save(update_fields=["estado"])

        seccion = self.crear_seccion("RUTA005")

        resultado = asignar_ruta_as_si_corresponde(seccion)

        self.assertIsNone(resultado)
        self.assertFalse(SeccionRuta.objects.filter(seccion=seccion).exists())

    def test_seccion_conserva_version_original(self):
        seccion_antigua = self.crear_seccion("RUTA006")

        ruta_antigua = asignar_ruta_as_si_corresponde(seccion_antigua)

        version_nueva = crear_nueva_version_ruta(self.version)

        actividad_nueva = version_nueva.actividades.get(orden=1)
        actividad_nueva.nombre = "Actividad actualizada para nueva versión"
        actividad_nueva.save()

        version_nueva.estado = "ACTIVA"
        version_nueva.save(update_fields=["estado"])

        seccion_nueva = self.crear_seccion("RUTA007")

        ruta_nueva = asignar_ruta_as_si_corresponde(seccion_nueva)

        ruta_antigua.refresh_from_db()
        ruta_nueva.refresh_from_db()

        self.assertEqual(ruta_antigua.ruta_version, self.version)
        self.assertEqual(ruta_nueva.ruta_version, version_nueva)

        self.assertEqual(ruta_antigua.actividades.count(), 23)
        self.assertEqual(ruta_nueva.actividades.count(), 23)

        actividad_antigua = ruta_antigua.actividades.get(
            ruta_actividad__orden=1
        )

        actividad_actualizada = ruta_nueva.actividades.get(
            ruta_actividad__orden=1
        )

        self.assertEqual(
            actividad_antigua.ruta_actividad.nombre,
            "Actividad 1"
        )

        self.assertEqual(
            actividad_actualizada.ruta_actividad.nombre,
            "Actividad actualizada para nueva versión"
        )
    def test_reasignacion_conserva_version_anterior(self):
        seccion = self.crear_seccion("RUTA008")

        ruta_original = asignar_ruta_as_si_corresponde(seccion)

        version_nueva = crear_nueva_version_ruta(self.version)
        version_nueva.estado = "ACTIVA"
        version_nueva.save(update_fields=["estado"])

        ruta_reasignada = asignar_ruta_as_si_corresponde(seccion)

        self.assertEqual(ruta_original.pk, ruta_reasignada.pk)
        self.assertEqual(ruta_reasignada.ruta_version, self.version)
        self.assertEqual(ruta_reasignada.actividades.count(), 23)


class SeguimientoRutaTestCase(TestCase):
    def setUp(self):
        Usuario = get_user_model()

        grupo_docente, _ = Group.objects.get_or_create(
            name="Docente"
        )
        grupo_coordinador, _ = Group.objects.get_or_create(
            name="Coordinador"
        )

        self.usuario_docente = Usuario.objects.create_user(
            username="docente_prueba",
            password="Prueba12345"
        )
        self.usuario_docente.groups.add(grupo_docente)

        self.usuario_otro = Usuario.objects.create_user(
            username="docente_otro",
            password="Prueba12345"
        )
        self.usuario_otro.groups.add(grupo_docente)

        self.usuario_coordinador = Usuario.objects.create_user(
            username="coordinador_prueba",
            password="Prueba12345"
        )
        self.usuario_coordinador.groups.add(grupo_coordinador)

        self.docente = Docente.objects.create(
            usuario=self.usuario_docente,
            rut="11111111-1",
            nombres="Docente",
            apellidos="Prueba",
            correo_institucional="docente.prueba@universidad.cl",
            activo=True
        )

        self.otro_docente = Docente.objects.create(
            usuario=self.usuario_otro,
            rut="22222222-2",
            nombres="Otro",
            apellidos="Docente",
            correo_institucional="otro.docente@universidad.cl",
            activo=True
        )

        sede = Sede.objects.create(
            nombre="Sede de Prueba",
            activo=True
        )

        campus = Campus.objects.create(
            sede=sede,
            nombre="Campus de Prueba",
            activo=True
        )

        asignatura = Asignatura.objects.create(
            codigo="HU02",
            nombre="Asignatura HU-02",
            activo=True
        )

        periodo = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="Primavera 2026",
            estado="Activo"
        )

        self.seccion = Seccion.objects.create(
            periodo=periodo,
            campus=campus,
            asignatura=asignatura,
            nrc="HU02001",
            seccion="1",
            estado="Activo"
        )

        SeccionDocente.objects.create(
            seccion=self.seccion,
            docente=self.docente
        )

        plantilla = RutaPlantilla.objects.create(
            nombre="Ruta HU-02",
            activo=True
        )

        version = RutaVersion.objects.create(
            plantilla=plantilla,
            numero_version=1,
            estado="BORRADOR"
        )

        self.ruta = SeccionRuta.objects.create(
            seccion=self.seccion,
            ruta_version=version,
            estado="EN_PROGRESO",
            porcentaje_final=0
        )

        actividad_obligatoria = RutaActividad.objects.create(
            ruta_version=version,
            etapa="Etapa de prueba",
            nombre="Actividad obligatoria",
            es_obligatoria=True,
            orden=1
        )

        actividad_opcional = RutaActividad.objects.create(
            ruta_version=version,
            etapa="Etapa de prueba",
            nombre="Actividad opcional",
            es_obligatoria=False,
            orden=2
        )
        version.estado = "ACTIVA"
        version.save(update_fields=["estado"])

        self.actividad_obligatoria = SeccionActividad.objects.create(
            seccion_ruta=self.ruta,
            ruta_actividad=actividad_obligatoria,
            estado="PENDIENTE"
        )

        self.actividad_opcional = SeccionActividad.objects.create(
            seccion_ruta=self.ruta,
            ruta_actividad=actividad_opcional,
            estado="PENDIENTE"
        )

    def test_docente_puede_ver_su_ruta(self):
        self.client.force_login(self.usuario_docente)

        respuesta = self.client.get(
            reverse(
                "rutas:detalle_ruta_docente",
                args=[self.ruta.id]
            )
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_otro_docente_no_puede_ver_ruta_ajena(self):
        self.client.force_login(self.usuario_otro)

        respuesta = self.client.get(
            reverse(
                "rutas:detalle_ruta_docente",
                args=[self.ruta.id]
            )
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_coordinador_puede_ver_seguimiento(self):
        self.client.force_login(self.usuario_coordinador)

        respuesta = self.client.get(
            reverse("rutas:seguimiento_rutas_coordinacion")
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_coordinador_puede_ver_detalle(self):
        self.client.force_login(self.usuario_coordinador)

        respuesta = self.client.get(
            reverse(
                "rutas:detalle_ruta_coordinacion",
                args=[self.ruta.id]
            )
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_coordinador_no_puede_completar_actividad(self):
        self.client.force_login(self.usuario_coordinador)

        respuesta = self.client.post(
            reverse(
                "rutas:completar_actividad",
                args=[self.actividad_obligatoria.id]
            )
        )

        self.assertEqual(respuesta.status_code, 403)

        self.actividad_obligatoria.refresh_from_db()

        self.assertIsNone(
            self.actividad_obligatoria.completada_por_docente
        )

    def test_avance_considera_solo_obligatorias(self):
        self.actividad_opcional.completada_por_docente = self.docente
        self.actividad_opcional.estado = "COMPLETADA"
        self.actividad_opcional.save()

        recalcular_avance(self.ruta)

        self.ruta.refresh_from_db()

        self.assertEqual(self.ruta.porcentaje_final, 0)

        self.actividad_obligatoria.completada_por_docente = self.docente
        self.actividad_obligatoria.estado = "COMPLETADA"
        self.actividad_obligatoria.save()

        recalcular_avance(self.ruta)

        self.ruta.refresh_from_db()

        self.assertEqual(self.ruta.porcentaje_final, 100)

    def test_no_puede_cerrar_ruta_con_obligatorias_pendientes(self):
        self.client.force_login(self.usuario_docente)

        respuesta = self.client.post(
            reverse(
                "rutas:completar_ruta",
                args=[self.ruta.id]
            )
        )

        self.ruta.refresh_from_db()

        self.assertNotEqual(self.ruta.estado, "COMPLETADA")
        self.assertNotEqual(self.ruta.porcentaje_final, 100)

    @patch("archivos.services.obtener_storage_privado", return_value=InMemoryStorage())
    def test_cualquier_actividad_acepta_evidencia(self, _storage):
        self.client.force_login(self.usuario_docente)

        self.client.post(
            reverse("rutas:subir_evidencia", args=[self.actividad_obligatoria.id]),
            {"archivo": SimpleUploadedFile("acuerdo.pdf", b"%PDF-1.4", content_type="application/pdf")},
        )

        self.assertEqual(self.actividad_obligatoria.evidencias.count(), 1)

    def test_recurso_url_reemplaza_seccion_y_actividad(self):
        ruta_actividad = self.actividad_obligatoria.ruta_actividad
        version = ruta_actividad.ruta_version
        version.estado = "BORRADOR"
        version.save(update_fields=["estado"])
        ruta_actividad.recurso_url = "/a/{seccion}/b/{actividad}/"
        ruta_actividad.save()
        version.estado = "ACTIVA"
        version.save(update_fields=["estado"])
        self.assertEqual(
            url_recurso(self.actividad_obligatoria),
            f"/a/{self.seccion.id}/b/{self.actividad_obligatoria.id}/",
        )

    def test_formularios_qr_muestra_solo_el_proceso_pedido(self):
        for titulo, proceso in (("Encuesta estudiantes", "EVALUACION_AS"), ("Otro formulario", "GENERAL")):
            version = encuestas_services.crear_formulario(titulo, proceso=proceso)
            version.estado = "PUBLICADA"
            version.save()
            EnlaceFormulario.objects.create(version=version, token=uuid.uuid4(), activo=True, fecha_inicio=timezone.now())

        self.client.force_login(self.usuario_docente)

        respuesta = self.client.get(reverse("rutas:formularios_qr") + "?proceso=EVALUACION_AS")

        self.assertContains(respuesta, "Encuesta estudiantes")
        self.assertNotContains(respuesta, "Otro formulario")



class CargarRutaDocenteTestCase(TestCase):
    def test_carga_orden_de_la_ruta_y_recursos(self):
        from django.core.management import call_command

        call_command("cargar_ruta_docente", stdout=open(os.devnull, "w"))

        actividades = {a.orden: a for a in RutaActividad.objects.all()}

        self.assertEqual(len(actividades), 23)
        self.assertEqual(actividades[18].nombre, "Organizar el evento de cierre")
        self.assertEqual(actividades[22].nombre, "Enviar documentación final")
        self.assertIn("{seccion}", actividades[10].recurso_url)
        self.assertIn("{actividad}", actividades[13].recurso_url)
        self.assertIn("proceso=EVALUACION_AS", actividades[19].recurso_url)


class CierreYExpedienteTestCase(TestCase):
    """CDE-518 (cierre e invitación), CDE-515 (pendientes) y CDE-522 (ZIP)."""

    def setUp(self):
        SeguimientoRutaTestCase.setUp(self)

        from socios.models import ContactoSocio, ParticipacionSocio, SocioComunitario

        ruta_cierre = self.actividad_obligatoria.ruta_actividad
        ruta_cierre.nombre = "Organizar el evento de cierre"
        ruta_cierre.config_recordatorio_json = {"recordatorio": "invitacion_cierre"}
        ruta_cierre.save()
        self.actividad_cierre = self.actividad_obligatoria

        self.socio = SocioComunitario.objects.create(
            nombre_organizacion="Junta de Vecinos",
            estado_revision="APROBADO",
            es_provisional=False,
            activo=True,
            fecha_creacion=timezone.now(),
        )
        ContactoSocio.objects.create(
            socio=self.socio,
            nombre="Contacto",
            correo="socio@example.com",
            es_principal=True,
            activo=True,
        )
        ParticipacionSocio.objects.create(
            socio=self.socio,
            seccion=self.seccion,
            origen="OPERATIVO",
        )

    def _invitar(self, modo):
        self.client.force_login(self.usuario_docente)
        return self.client.post(
            reverse("rutas:invitar_socios_cierre", args=[self.actividad_cierre.id]),
            {"socios": [self.socio.id], "modo_contacto": modo},
        )

    def test_sin_cierre_completa_la_actividad_sin_incumplimiento(self):
        self.client.force_login(self.usuario_docente)

        self.client.post(reverse("rutas:indicar_sin_cierre", args=[self.actividad_cierre.id]))

        self.actividad_cierre.refresh_from_db()
        self.ruta.refresh_from_db()
        self.assertEqual(self.actividad_cierre.estado, "COMPLETADA")
        self.assertEqual(self.actividad_cierre.observacion, "No habrá actividad de cierre.")
        self.assertEqual(self.ruta.porcentaje_final, 100)

    def test_sin_cierre_solo_en_la_actividad_de_cierre(self):
        self.client.force_login(self.usuario_docente)

        respuesta = self.client.post(
            reverse("rutas:indicar_sin_cierre", args=[self.actividad_opcional.id])
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_invitacion_por_plataforma_envia_enlaces_unicos(self):
        from django.core import mail
        from socios.models import InvitacionCierre

        self._invitar("PLATAFORMA")

        invitacion = InvitacionCierre.objects.get()
        self.assertEqual(invitacion.respuesta, "SIN_RESPUESTA")
        self.assertIsNotNone(invitacion.fecha_envio)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"/rutas/cierre/{invitacion.token}/asistire/", mail.outbox[0].body)
        self.assertIn(f"/rutas/cierre/{invitacion.token}/no-asistire/", mail.outbox[0].body)
        # La invitación no completa ni bloquea la Ruta.
        self.actividad_cierre.refresh_from_db()
        self.assertEqual(self.actividad_cierre.estado, "PENDIENTE")

    def test_socio_responde_desde_pagina_publica_sin_barra(self):
        from socios.models import InvitacionCierre

        self._invitar("PLATAFORMA")
        self.client.logout()
        invitacion = InvitacionCierre.objects.get()
        url = reverse("rutas:responder_invitacion_cierre", args=[invitacion.token, "asistire"])

        pagina = self.client.get(url)
        invitacion.refresh_from_db()
        self.assertEqual(invitacion.respuesta, "SIN_RESPUESTA")
        self.assertNotContains(pagina, "navbar-sistema")
        self.assertContains(pagina, "Junta de Vecinos")

        self.client.post(url)
        invitacion.refresh_from_db()
        self.assertEqual(invitacion.respuesta, "ASISTIRA")
        self.assertIsNotNone(invitacion.fecha_respuesta)

    def test_contacto_externo_docente_registra_resultado(self):
        from django.core import mail
        from socios.models import InvitacionCierre

        self._invitar("EXTERNO")
        invitacion = InvitacionCierre.objects.get()
        self.assertEqual(len(mail.outbox), 0)

        self.client.post(
            reverse("rutas:registrar_respuesta_cierre", args=[invitacion.id]),
            {"respuesta": "NO"},
        )

        invitacion.refresh_from_db()
        self.assertEqual(invitacion.respuesta, "NO")

    def test_panel_docente_lista_pendientes_e_invitacion(self):
        self.client.force_login(self.usuario_docente)

        respuesta = self.client.get(reverse("core:inicio_docente"))
        self.assertContains(respuesta, "indica si habrá cierre e invita al Socio")
        self.assertContains(respuesta, "Actividad opcional (opcional)")

        self._invitar("EXTERNO")
        respuesta = self.client.get(reverse("core:inicio_docente"))
        self.assertContains(respuesta, "Registrar si Junta de Vecinos asistirá al cierre")

    @patch("archivos.services.obtener_storage_privado")
    def test_coordinacion_descarga_zip_con_solo_ese_expediente(self, obtener_storage):
        import io
        import zipfile

        from academico.models import Carrera, Facultad, SeccionCarrera

        obtener_storage.return_value = InMemoryStorage()

        facultad = Facultad.objects.create(nombre="Ingeniería", activo=True)
        carrera = Carrera.objects.create(facultad=facultad, nombre="Ingeniería Civil Informática", activo=True)
        SeccionCarrera.objects.create(seccion=self.seccion, carrera=carrera, declaracion_as=True)

        self.client.force_login(self.usuario_docente)
        self.client.post(
            reverse("rutas:subir_evidencia", args=[self.actividad_cierre.id]),
            {"archivo": SimpleUploadedFile("acuerdo.pdf", b"%PDF-1.4", content_type="application/pdf")},
        )

        url = reverse("rutas:descargar_expediente", args=[self.ruta.id])
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.usuario_coordinador)
        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(
            "campus-de-prueba_sede-de-prueba_2026_primavera-2026_ingenieria-civil-informatica_"
            "asignatura-hu-02_seccion-1_docente-prueba.zip",
            respuesta["Content-Disposition"],
        )

        contenido = zipfile.ZipFile(io.BytesIO(b"".join(respuesta.streaming_content)))
        self.assertEqual(contenido.namelist(), ["01 - Organizar el evento de cierre/acuerdo.pdf"])

    @patch("archivos.services.obtener_storage_privado", return_value=InMemoryStorage())
    def test_cualquier_actividad_acepta_evidencia(self, _storage):
        self.client.force_login(self.usuario_docente)

        self.client.post(
            reverse("rutas:subir_evidencia", args=[self.actividad_obligatoria.id]),
            {"archivo": SimpleUploadedFile("acuerdo.pdf", b"%PDF-1.4", content_type="application/pdf")},
        )

        self.assertEqual(self.actividad_obligatoria.evidencias.count(), 1)

    def test_recurso_url_reemplaza_seccion_y_actividad(self):
        ruta_actividad = self.actividad_obligatoria.ruta_actividad
        ruta_actividad.recurso_url = "/a/{seccion}/b/{actividad}/"
        ruta_actividad.save()

        self.assertEqual(
            url_recurso(self.actividad_obligatoria),
            f"/a/{self.seccion.id}/b/{self.actividad_obligatoria.id}/",
        )

    def test_formularios_qr_muestra_solo_el_proceso_pedido(self):
        for titulo, proceso in (("Encuesta estudiantes", "EVALUACION_AS"), ("Otro formulario", "GENERAL")):
            version = encuestas_services.crear_formulario(titulo, proceso=proceso)
            version.estado = "PUBLICADA"
            version.save()
            EnlaceFormulario.objects.create(version=version, token=uuid.uuid4(), activo=True, fecha_inicio=timezone.now())

        self.client.force_login(self.usuario_docente)

        respuesta = self.client.get(reverse("rutas:formularios_qr") + "?proceso=EVALUACION_AS")

        self.assertContains(respuesta, "Encuesta estudiantes")
        self.assertNotContains(respuesta, "Otro formulario")



class CargarRutaDocenteTestCase(TestCase):
    def test_carga_orden_de_la_ruta_y_recursos(self):
        from django.core.management import call_command

        call_command("cargar_ruta_docente", stdout=open(os.devnull, "w"))

        actividades = {a.orden: a for a in RutaActividad.objects.all()}

        self.assertEqual(len(actividades), 23)
        self.assertEqual(actividades[18].nombre, "Organizar el evento de cierre")
        self.assertEqual(actividades[22].nombre, "Enviar documentación final")
        self.assertIn("{seccion}", actividades[10].recurso_url)
        self.assertIn("{actividad}", actividades[13].recurso_url)
        self.assertIn("proceso=EVALUACION_AS", actividades[19].recurso_url)


class CierreYExpedienteTestCase(TestCase):
    def setUp(self):
        SeguimientoRutaTestCase.setUp(self)

        from socios.models import ContactoSocio, ParticipacionSocio, SocioComunitario

        ruta_cierre = self.actividad_obligatoria.ruta_actividad
        version = ruta_cierre.ruta_version
        version.estado = "BORRADOR"
        version.save(update_fields=["estado"])
        ruta_cierre.nombre = "Organizar el evento de cierre"
        ruta_cierre.config_recordatorio_json = {
            "recordatorio": "invitacion_cierre"
        }
        ruta_cierre.save()
        version.estado = "ACTIVA"
        version.save(update_fields=["estado"])

        self.actividad_cierre = self.actividad_obligatoria

        self.socio = SocioComunitario.objects.create(
            nombre_organizacion="Junta de Vecinos",
            estado_revision="APROBADO",
            es_provisional=False,
            activo=True,
            fecha_creacion=timezone.now(),
        )
        ContactoSocio.objects.create(
            socio=self.socio,
            nombre="Contacto",
            correo="socio@example.com",
            es_principal=True,
            activo=True,
        )
        ParticipacionSocio.objects.create(
            socio=self.socio,
            seccion=self.seccion,
            origen="OPERATIVO",
        )

    def _invitar(self, modo):
        self.client.force_login(self.usuario_docente)
        return self.client.post(
            reverse("rutas:invitar_socios_cierre", args=[self.actividad_cierre.id]),
            {"socios": [self.socio.id], "modo_contacto": modo},
        )

    def test_sin_cierre_completa_la_actividad_sin_incumplimiento(self):
        self.client.force_login(self.usuario_docente)

        self.client.post(reverse("rutas:indicar_sin_cierre", args=[self.actividad_cierre.id]))

        self.actividad_cierre.refresh_from_db()
        self.ruta.refresh_from_db()
        self.assertEqual(self.actividad_cierre.estado, "COMPLETADA")
        self.assertEqual(self.actividad_cierre.observacion, "No habrá actividad de cierre.")
        self.assertEqual(self.ruta.porcentaje_final, 100)

    def test_sin_cierre_solo_en_la_actividad_de_cierre(self):
        self.client.force_login(self.usuario_docente)

        respuesta = self.client.post(
            reverse("rutas:indicar_sin_cierre", args=[self.actividad_opcional.id])
        )

        self.assertEqual(respuesta.status_code, 403)

    def test_invitacion_por_plataforma_envia_enlaces_unicos(self):
        from django.core import mail
        from socios.models import InvitacionCierre

        self._invitar("PLATAFORMA")

        invitacion = InvitacionCierre.objects.get()
        self.assertEqual(invitacion.respuesta, "SIN_RESPUESTA")
        self.assertIsNotNone(invitacion.fecha_envio)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"/rutas/cierre/{invitacion.token}/asistire/", mail.outbox[0].body)
        self.assertIn(f"/rutas/cierre/{invitacion.token}/no-asistire/", mail.outbox[0].body)
        # La invitación no completa ni bloquea la Ruta.
        self.actividad_cierre.refresh_from_db()
        self.assertEqual(self.actividad_cierre.estado, "PENDIENTE")

    def test_socio_responde_desde_pagina_publica_sin_barra(self):
        from socios.models import InvitacionCierre

        self._invitar("PLATAFORMA")
        self.client.logout()
        invitacion = InvitacionCierre.objects.get()
        url = reverse("rutas:responder_invitacion_cierre", args=[invitacion.token, "asistire"])

        pagina = self.client.get(url)
        invitacion.refresh_from_db()
        self.assertEqual(invitacion.respuesta, "SIN_RESPUESTA")
        self.assertNotContains(pagina, "navbar-sistema")
        self.assertContains(pagina, "Junta de Vecinos")

        self.client.post(url)
        invitacion.refresh_from_db()
        self.assertEqual(invitacion.respuesta, "ASISTIRA")
        self.assertIsNotNone(invitacion.fecha_respuesta)

    def test_contacto_externo_docente_registra_resultado(self):
        from django.core import mail
        from socios.models import InvitacionCierre

        self._invitar("EXTERNO")
        invitacion = InvitacionCierre.objects.get()
        self.assertEqual(len(mail.outbox), 0)

        self.client.post(
            reverse("rutas:registrar_respuesta_cierre", args=[invitacion.id]),
            {"respuesta": "NO"},
        )

        invitacion.refresh_from_db()
        self.assertEqual(invitacion.respuesta, "NO")

    def test_panel_docente_lista_pendientes_e_invitacion(self):
        self.client.force_login(self.usuario_docente)

        respuesta = self.client.get(reverse("core:inicio_docente"))
        self.assertContains(respuesta, "indica si habrá cierre e invita al Socio")
        self.assertContains(respuesta, "Actividad opcional (opcional)")

        self._invitar("EXTERNO")
        respuesta = self.client.get(reverse("core:inicio_docente"))
        self.assertContains(respuesta, "Registrar si Junta de Vecinos asistirá al cierre")

    @patch("archivos.services.obtener_storage_privado")
    def test_coordinacion_descarga_zip_con_solo_ese_expediente(self, obtener_storage):
        import io
        import zipfile

        from academico.models import Carrera, Facultad, SeccionCarrera

        obtener_storage.return_value = InMemoryStorage()

        facultad = Facultad.objects.create(nombre="Ingeniería", activo=True)
        carrera = Carrera.objects.create(facultad=facultad, nombre="Ingeniería Civil Informática", activo=True)
        SeccionCarrera.objects.create(seccion=self.seccion, carrera=carrera, declaracion_as=True)

        self.client.force_login(self.usuario_docente)
        self.client.post(
            reverse("rutas:subir_evidencia", args=[self.actividad_cierre.id]),
            {"archivo": SimpleUploadedFile("acuerdo.pdf", b"%PDF-1.4", content_type="application/pdf")},
        )

        url = reverse("rutas:descargar_expediente", args=[self.ruta.id])
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.usuario_coordinador)
        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(
            "campus-de-prueba_sede-de-prueba_2026_primavera-2026_ingenieria-civil-informatica_"
            "asignatura-hu-02_seccion-1_docente-prueba.zip",
            respuesta["Content-Disposition"],
        )

        contenido = zipfile.ZipFile(io.BytesIO(b"".join(respuesta.streaming_content)))
        self.assertEqual(contenido.namelist(), ["01 - Organizar el evento de cierre/acuerdo.pdf"])

class VersionadoRutaTestCase(TestCase):
    def setUp(self):
        self.plantilla = RutaPlantilla.objects.create(
            nombre="Ruta del Docente A+S",
            descripcion="Ruta de prueba",
            activo=True,
        )

        self.version_original = RutaVersion.objects.create(
            plantilla=self.plantilla,
            numero_version=1,
            estado="BORRADOR",
        )

        for numero in range(1, 24):
            RutaActividad.objects.create(
                ruta_version=self.version_original,
                etapa=f"Etapa {(numero - 1) // 5 + 1}",
                nombre=f"Actividad {numero}",
                descripcion=f"Descripción {numero}",
                es_obligatoria=True,
                orden=numero,
            )

        self.version_original.estado = "ACTIVA"
        self.version_original.save()

    def test_crea_una_nueva_version(self):
        nueva_version = crear_nueva_version_ruta(self.version_original)

        self.assertEqual(nueva_version.numero_version, 2)
        self.assertEqual(nueva_version.estado, "BORRADOR")
        self.assertEqual(nueva_version.plantilla, self.plantilla)

    def test_copia_las_23_actividades(self):
        nueva_version = crear_nueva_version_ruta(self.version_original)

        self.assertEqual(nueva_version.actividades.count(), 23)
        self.assertEqual(self.version_original.actividades.count(), 23)

    def test_conserva_actividades_obligatorias(self):
        nueva_version = crear_nueva_version_ruta(self.version_original)

        self.assertEqual(
            nueva_version.actividades.filter(es_obligatoria=True).count(),
            23,
        )

    def test_no_modifica_la_version_original(self):
        nueva_version = crear_nueva_version_ruta(self.version_original)

        actividad_nueva = nueva_version.actividades.get(orden=1)
        actividad_nueva.nombre = "Actividad modificada"
        actividad_nueva.save()

        actividad_original = self.version_original.actividades.get(orden=1)

        self.assertEqual(actividad_original.nombre, "Actividad 1")
        self.assertEqual(actividad_nueva.nombre, "Actividad modificada")

    def test_genera_numeros_consecutivos(self):
        version_dos = crear_nueva_version_ruta(self.version_original)
        version_tres = crear_nueva_version_ruta(version_dos)

        self.assertEqual(version_dos.numero_version, 2)
        self.assertEqual(version_tres.numero_version, 3)

    def test_no_comparte_registros_de_actividades(self):
        nueva_version = crear_nueva_version_ruta(self.version_original)

        ids_originales = set(
            self.version_original.actividades.values_list("id", flat=True)
        )
        ids_nuevos = set(
            nueva_version.actividades.values_list("id", flat=True)
        )

        self.assertTrue(ids_originales.isdisjoint(ids_nuevos))
    def test_no_permite_modificar_actividad_publicada(self):
        actividad = self.version_original.actividades.get(orden=1)

        actividad.nombre = "Actividad modificada"

        with self.assertRaises(ValidationError):
            actividad.save()

        actividad.refresh_from_db()

        self.assertEqual(actividad.nombre, "Actividad 1")

    def test_no_permite_eliminar_actividad_publicada(self):
        actividad = self.version_original.actividades.get(orden=1)

        with self.assertRaises(ValidationError):
            actividad.delete()

        self.assertTrue(
            RutaActividad.objects.filter(pk=actividad.pk).exists()
        )

    def test_permite_modificar_actividad_en_borrador(self):
        nueva_version = crear_nueva_version_ruta(self.version_original)

        actividad = nueva_version.actividades.get(orden=1)
        actividad.nombre = "Actividad actualizada"
        actividad.save()

        actividad.refresh_from_db()

        self.assertEqual(actividad.nombre, "Actividad actualizada")

    def test_no_permite_update_en_version_publicada(self):
        actividad = self.version_original.actividades.get(orden=1)
        nombre_original = actividad.nombre

        with self.assertRaises(ValidationError):
            RutaActividad.objects.filter(pk=actividad.pk).update(
                nombre="Actividad modificada"
            )

        actividad.refresh_from_db()
        self.assertEqual(actividad.nombre, nombre_original)

    def test_no_permite_bulk_update_en_version_publicada(self):
        actividad = self.version_original.actividades.get(orden=1)
        nombre_original = actividad.nombre
        actividad.nombre = "Actividad modificada"

        with self.assertRaises(ValidationError):
            RutaActividad.objects.bulk_update(
                [actividad], ["nombre"]
            )

        actividad.refresh_from_db()
        self.assertEqual(actividad.nombre, nombre_original)

    def test_no_permite_delete_masivo_en_version_publicada(self):
        actividad = self.version_original.actividades.get(orden=1)

        with self.assertRaises(ValidationError):
            RutaActividad.objects.filter(pk=actividad.pk).delete()

        self.assertTrue(
            RutaActividad.objects.filter(pk=actividad.pk).exists()
        )
    def test_no_permite_bulk_create_en_version_publicada(self):
        nueva_actividad = RutaActividad(
            ruta_version=self.version_original,
            etapa="Etapa nueva",
            nombre="Actividad no permitida",
            es_obligatoria=True,
            orden=24,
        )

        with self.assertRaises(ValidationError):
            RutaActividad.objects.bulk_create([nueva_actividad])

        self.assertEqual(
            self.version_original.actividades.count(),
            23,
        )
class AuditoriaYPruebasAvanzadasRutaTestCase(SeguimientoRutaTestCase):
    """
    CDE-528 / CDE-529 / CDE-530: Cobertura de auditoría, porcentaje,
    cierre, evidencias y control de acceso a secciones ajenas.
    """

    def test_auditoria_al_completar_desmarcar_actividad(self):
        self.client.force_login(self.usuario_docente)

        # 1. Completar actividad
        self.client.post(
            reverse("rutas:completar_actividad", args=[self.actividad_obligatoria.id])
        )
        auditoria_marcar = AuditoriaCambio.objects.filter(
            entidad="SeccionActividad",
            entidad_id=self.actividad_obligatoria.id,
            accion="MARCAR_ACTIVIDAD",
        ).first()

        self.assertIsNotNone(auditoria_marcar)
        self.assertEqual(auditoria_marcar.valores_nuevos_json.get("estado"), "COMPLETADA")

        # 2. Desmarcar actividad
        self.client.post(
            reverse("rutas:completar_actividad", args=[self.actividad_obligatoria.id])
        )
        auditoria_desmarcar = AuditoriaCambio.objects.filter(
            entidad="SeccionActividad",
            entidad_id=self.actividad_obligatoria.id,
            accion="DESMARCAR_ACTIVIDAD",
        ).first()

        self.assertIsNotNone(auditoria_desmarcar)
        self.assertEqual(auditoria_desmarcar.valores_nuevos_json.get("estado"), "PENDIENTE")

    @patch("archivos.services.obtener_storage_privado", return_value=InMemoryStorage())
    def test_auditoria_al_subir_y_eliminar_evidencia(self, _storage):
        self.client.force_login(self.usuario_docente)

        # 1. Subir evidencia
        self.client.post(
            reverse("rutas:subir_evidencia", args=[self.actividad_obligatoria.id]),
            {"archivo": SimpleUploadedFile("informe.pdf", b"%PDF-1.4", content_type="application/pdf")},
        )
        evidencia = self.actividad_obligatoria.evidencias.first()
        self.assertIsNotNone(evidencia)

        auditoria_subir = AuditoriaCambio.objects.filter(
            entidad="Evidencia",
            entidad_id=evidencia.pk,
            accion="SUBIR_EVIDENCIA",
        ).first()
        self.assertIsNotNone(auditoria_subir)

        # 2. Eliminar evidencia
        self.client.post(reverse("rutas:eliminar_evidencia", args=[evidencia.id]))
        auditoria_eliminar = AuditoriaCambio.objects.filter(
            entidad="Evidencia",
            entidad_id=evidencia.pk,
            accion="ELIMINAR_EVIDENCIA",
        ).first()
        self.assertIsNotNone(auditoria_eliminar)

    def test_auditoria_al_completar_ruta(self):
        self.client.force_login(self.usuario_docente)

        # Marcar actividad obligatoria para permitir el cierre
        self.actividad_obligatoria.completada_por_docente = self.docente
        self.actividad_obligatoria.estado = "COMPLETADA"
        self.actividad_obligatoria.save()

        self.client.post(reverse("rutas:completar_ruta", args=[self.ruta.id]))

        auditoria_cierre = AuditoriaCambio.objects.filter(
            entidad="SeccionRuta",
            entidad_id=self.ruta.id,
            accion="COMPLETAR_RUTA",
        ).first()

        self.assertIsNotNone(auditoria_cierre)
        self.assertEqual(auditoria_cierre.valores_nuevos_json.get("estado"), "COMPLETADA")

    def test_docente_no_puede_modificar_actividad_seccion_ajena(self):
        self.client.force_login(self.usuario_otro)

        respuesta = self.client.post(
            reverse("rutas:completar_actividad", args=[self.actividad_obligatoria.id])
        )
        self.assertEqual(respuesta.status_code, 403)

    @patch("archivos.services.obtener_storage_privado", return_value=InMemoryStorage())
    def test_docente_no_puede_subir_evidencia_seccion_ajena(self, _storage):
        self.client.force_login(self.usuario_otro)

        respuesta = self.client.post(
            reverse("rutas:subir_evidencia", args=[self.actividad_obligatoria.id]),
            {"archivo": SimpleUploadedFile("hack.pdf", b"%PDF-1.4", content_type="application/pdf")},
        )
        self.assertEqual(respuesta.status_code, 403)