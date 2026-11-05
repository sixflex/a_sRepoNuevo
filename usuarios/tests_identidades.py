"""Una persona = un Usuario, entre con @uautonoma.cl o con @cloud.uautonoma.cl."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academico.models import Asignatura, Campus, Docente, PeriodoAcademico, Seccion, SeccionDocente, Sede
from archivos.models import Archivo
from auditoria.models import AuditoriaCambio
from cartas.models import EnlaceSolicitudCarta, SolicitudCarta
from proyectos.models import EnlaceRegistroEquipo, Equipo

from . import services
from .models import IdentidadInstitucional


Usuario = get_user_model()

UA = "docente@uautonoma.cl"
CLOUD = "docente@cloud.uautonoma.cl"


@override_settings(ENTRA_MODO="simulado", ENTRA_DOMINIO_PERMITIDO=None, ENTRA_DOMINIOS_PERMITIDOS=None)
class BaseIdentidades(TestCase):
    def ingresar(self, correo, **extra):
        return self.client.post(reverse("usuarios:entra_login"), {"correo": correo, **extra})

    def usuario_en_sesion(self):
        return Usuario.objects.get(pk=self.client.session["_auth_user_id"])

    def vincular(self, correo):
        self.client.post(reverse("usuarios:cuenta_vincular"))
        return self.ingresar(correo)


class DominiosTests(BaseIdentidades):
    def test_se_aceptan_los_dos_dominios(self):
        for correo in ("ana@uautonoma.cl", "ana@cloud.uautonoma.cl"):
            with self.subTest(correo=correo):
                self.client.logout()
                self.ingresar(correo)
                self.assertEqual(self.usuario_en_sesion().correo_institucional, correo)

    def test_otros_dominios_se_rechazan_y_el_mensaje_nombra_ambos(self):
        for correo in ("ana@gmail.com", "ana@mail.uautonoma.cl", "ana@cloud.uautonoma.cl.evil.com"):
            with self.subTest(correo=correo):
                respuesta = self.ingresar(correo)
                self.assertContains(respuesta, "@uautonoma.cl o @cloud.uautonoma.cl")
                self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(ENTRA_DOMINIO_PERMITIDO="uautonoma.cl")
    def test_la_variable_antigua_de_un_dominio_sigue_mandando(self):
        respuesta = self.ingresar("ana@cloud.uautonoma.cl")
        self.assertContains(respuesta, "Solo se permiten cuentas institucionales @uautonoma.cl.")

    def test_segundo_acceso_reutiliza_usuario_e_identidad(self):
        self.ingresar(CLOUD)
        self.client.logout()
        self.ingresar(CLOUD)
        self.assertEqual(Usuario.objects.count(), 1)
        identidad = IdentidadInstitucional.objects.get()
        self.assertTrue(identidad.es_principal)
        self.assertEqual(identidad.tenant_id, "simulado")
        self.assertEqual(self.client.session[services.SESION_IDENTIDAD], identidad.pk)

    def test_usuario_antiguo_sin_identidad_recibe_la_suya_al_entrar(self):
        antiguo = Usuario.objects.create_user(username="x", correo_institucional=UA)
        self.ingresar(UA)
        self.assertEqual(self.usuario_en_sesion(), antiguo)
        self.assertEqual(antiguo.identidades.get().correo, UA)


class VincularTests(BaseIdentidades):
    def setUp(self):
        sede = Sede.objects.create(nombre="Sede", activo=True)
        campus = Campus.objects.create(sede=sede, nombre="Campus", activo=True)
        periodo = PeriodoAcademico.objects.create(anio=2026, nombre="2026")
        asignatura = Asignatura.objects.create(codigo="AS1", nombre="Taller A+S", activo=True)
        self.seccion = Seccion.objects.create(
            periodo=periodo, campus=campus, asignatura=asignatura, nrc="777", seccion="1", estado="ACTIVA",
        )
        # Coordinación lo registró con su correo @uautonoma.cl.
        self.docente = Docente.objects.create(
            rut="11111111-1", nombres="Docente", apellidos="Prueba", correo_institucional=UA, activo=True,
        )
        SeccionDocente.objects.create(seccion=self.seccion, docente=self.docente)

    def test_login_enlaza_al_docente_registrado_con_su_correo(self):
        self.ingresar(UA)
        usuario = self.usuario_en_sesion()
        self.assertEqual(usuario.perfil_docente, self.docente)
        self.assertTrue(usuario.groups.filter(name="Docente").exists())

    def test_no_se_roba_un_docente_de_otro_usuario(self):
        otro = Usuario.objects.create_user(username="otro")
        self.docente.usuario = otro
        self.docente.save()
        self.ingresar(UA)
        self.docente.refresh_from_db()
        self.assertEqual(self.docente.usuario, otro)

    def test_vincular_cuenta_libre_y_entrar_con_cualquiera(self):
        self.ingresar(UA)
        usuario = self.usuario_en_sesion()

        respuesta = self.vincular(CLOUD)
        self.assertRedirects(respuesta, reverse("usuarios:cuenta"), fetch_redirect_response=False)
        self.assertEqual(self.usuario_en_sesion(), usuario, "la sesión sigue siendo la misma")
        cloud = IdentidadInstitucional.objects.get(correo=CLOUD)
        self.assertEqual(cloud.usuario, usuario)
        self.assertEqual(cloud.origen_vinculo, IdentidadInstitucional.CONFIRMADO_USUARIO)
        self.assertFalse(cloud.es_principal)

        self.client.logout()
        self.ingresar(CLOUD)
        self.assertEqual(self.usuario_en_sesion(), usuario)
        # Mismo panel docente: ve su sección.
        panel = self.client.get(reverse("core:inicio_docente"))
        self.assertEqual(panel.status_code, 200)
        self.assertEqual(panel.context["total_secciones"], 1)

    def test_vincular_no_se_activa_sin_pedirlo_desde_mi_cuenta(self):
        self.ingresar(UA)
        self.ingresar(CLOUD)  # cambio de cuenta normal, no vinculación
        self.assertEqual(self.usuario_en_sesion().correo_institucional, CLOUD)
        self.assertEqual(Usuario.objects.count(), 2)

    def test_vincular_cuenta_con_datos_pide_confirmar_y_fusiona(self):
        # Primero entró con la cloud y quedó como otra persona, con datos.
        self.ingresar(CLOUD)
        cloud_usuario = self.usuario_en_sesion()
        archivo = Archivo.objects.create(
            cargado_por_usuario=cloud_usuario, nombre_original="e.pdf", extension="pdf",
            storage_key="x/e.pdf", mime_type="application/pdf", tamano_bytes=1, hash_sha256="a" * 64,
        )
        self.client.logout()

        self.ingresar(UA)
        usuario = self.usuario_en_sesion()
        respuesta = self.vincular(CLOUD)
        self.assertRedirects(respuesta, reverse("usuarios:cuenta_fusionar"), fetch_redirect_response=False)
        confirmacion = self.client.get(reverse("usuarios:cuenta_fusionar"))
        self.assertContains(confirmacion, CLOUD)
        self.assertContains(confirmacion, "Sí, unir cuentas")

        self.client.post(reverse("usuarios:cuenta_fusionar"), {"accion": "confirmar"})
        archivo.refresh_from_db()
        cloud_usuario.refresh_from_db()
        self.assertEqual(archivo.cargado_por_usuario, usuario)
        self.assertFalse(cloud_usuario.is_active)
        self.assertEqual(IdentidadInstitucional.objects.get(correo=CLOUD).usuario, usuario)

        self.client.logout()
        self.ingresar(CLOUD)
        self.assertEqual(self.usuario_en_sesion(), usuario)

    def test_fusion_se_puede_cancelar(self):
        self.ingresar(CLOUD)
        cloud_usuario = self.usuario_en_sesion()
        self.client.logout()
        self.ingresar(UA)
        self.vincular(CLOUD)
        self.client.post(reverse("usuarios:cuenta_fusionar"), {"accion": "cancelar"})
        cloud_usuario.refresh_from_db()
        self.assertTrue(cloud_usuario.is_active)

    def test_mi_cuenta_muestra_cuentas_y_acciones(self):
        self.ingresar(UA)
        self.vincular(CLOUD)
        respuesta = self.client.get(reverse("usuarios:cuenta"))
        self.assertContains(respuesta, UA)
        self.assertContains(respuesta, CLOUD)
        self.assertContains(respuesta, "Principal")
        self.assertContains(respuesta, "En uso ahora")
        self.assertContains(respuesta, "Vincular otra cuenta institucional")
        self.assertContains(respuesta, "Desvincular", count=1)  # no la que está en uso

    def test_usar_como_principal_y_desvincular(self):
        self.ingresar(UA)
        self.vincular(CLOUD)
        usuario = self.usuario_en_sesion()
        cloud = IdentidadInstitucional.objects.get(correo=CLOUD)
        ua = IdentidadInstitucional.objects.get(correo=UA)

        self.client.post(reverse("usuarios:cuenta_principal", args=[cloud.pk]))
        usuario.refresh_from_db()
        self.assertEqual(usuario.correo_institucional, CLOUD)

        # La que está en uso no se puede quitar.
        self.client.post(reverse("usuarios:cuenta_desvincular", args=[ua.pk]))
        self.assertTrue(IdentidadInstitucional.objects.filter(pk=ua.pk).exists())

        self.client.post(reverse("usuarios:cuenta_desvincular", args=[cloud.pk]))
        self.assertFalse(IdentidadInstitucional.objects.filter(pk=cloud.pk).exists())
        usuario.refresh_from_db()
        self.assertEqual(usuario.correo_institucional, UA)
        self.assertTrue(IdentidadInstitucional.objects.get(pk=ua.pk).es_principal)

    def test_no_se_desvincula_la_unica_cuenta(self):
        self.ingresar(UA)
        ua = IdentidadInstitucional.objects.get(correo=UA)
        with self.assertRaises(services.IdentidadError):
            services.desvincular_identidad(ua.usuario, ua)

    def test_planificacion_encuentra_al_docente_por_su_otro_correo(self):
        from planificacion.services import _resolver_docente

        self.ingresar(UA)
        self.vincular(CLOUD)

        class Fila:
            rut = ""
            correo = CLOUD.upper()

        self.assertEqual(_resolver_docente(Fila()), self.docente)

    def test_academico_rechaza_el_correo_vinculado_de_otra_persona(self):
        from academico.views import _correo_de_otra_persona

        self.ingresar(UA)
        self.vincular(CLOUD)
        nuevo = Docente(rut="22222222-2", nombres="Otra", apellidos="Persona", correo_institucional=CLOUD)
        self.assertIn("ya está registrada", _correo_de_otra_persona(nuevo))
        self.assertIsNone(_correo_de_otra_persona(self.docente))


class FusionarTests(TestCase):
    def setUp(self):
        self.origen = Usuario.objects.create_user(username="cloud", correo_institucional=CLOUD)
        self.destino = Usuario.objects.create_user(username="ua", correo_institucional=UA)
        services.asegurar_identidad_principal(self.origen)
        services.asegurar_identidad_principal(self.destino)
        self.origen.groups.add(Group.objects.create(name="Estudiante"))
        self.destino.groups.add(Group.objects.create(name="Docente"))

    def crear_solicitud(self, usuario):
        sede = Sede.objects.create(nombre="S", activo=True)
        campus = Campus.objects.create(sede=sede, nombre="C", activo=True)
        seccion = Seccion.objects.create(
            periodo=PeriodoAcademico.objects.create(anio=2026, nombre="P"), campus=campus,
            asignatura=Asignatura.objects.create(codigo="A", nombre="A", activo=True),
            nrc="1", seccion="1", estado="ACTIVA",
        )
        derivador = Docente.objects.create(
            rut="3-5", nombres="Profe", apellidos="Guía", correo_institucional="guia@uautonoma.cl", activo=True,
        )
        return SolicitudCarta.objects.create(
            seccion=seccion, campus=campus, sede=sede, solicitante_usuario=usuario, docente_derivador=derivador,
            solicitante_tipo="ESTUDIANTE", solicitante_nombre="X", solicitante_correo=CLOUD,
            estado="PENDIENTE", institucion_receptora="I", persona_receptora="P",
            fecha_solicitud=timezone.now(),
        )

    def test_mueve_llaves_foraneas_identidades_y_desactiva_origen(self):
        solicitud = self.crear_solicitud(self.origen)
        archivo = Archivo.objects.create(
            cargado_por_usuario=self.origen, nombre_original="e.pdf", extension="pdf",
            storage_key="x/e.pdf", mime_type="application/pdf", tamano_bytes=1, hash_sha256="b" * 64,
        )
        docente = Docente.objects.create(
            usuario=self.origen, rut="1-9", nombres="D", apellidos="P", correo_institucional=CLOUD, activo=True,
        )

        services.fusionar_usuarios(self.origen, self.destino)

        for objeto in (solicitud, archivo, docente):
            objeto.refresh_from_db()
        self.origen.refresh_from_db()
        self.destino.refresh_from_db()
        self.assertEqual(solicitud.solicitante_usuario, self.destino)
        self.assertEqual(archivo.cargado_por_usuario, self.destino)
        self.assertEqual(docente.usuario, self.destino)
        self.assertEqual(services.correos_de_usuario(self.destino), {UA, CLOUD})
        self.assertEqual(self.destino.identidades.filter(es_principal=True).get().correo, UA)
        self.assertFalse(self.origen.is_active)
        self.assertFalse(self.origen.activo)
        self.assertIsNone(self.origen.correo_institucional)
        # Docente gana sobre Estudiante.
        self.assertEqual(list(self.destino.groups.values_list("name", flat=True)), ["Docente"])
        self.assertTrue(AuditoriaCambio.objects.filter(accion="FUSIONAR_CUENTAS").exists())
        self.assertEqual(services.usuario_por_correo(CLOUD), self.destino)

    def test_dos_docentes_distintos_no_se_fusionan(self):
        Docente.objects.create(usuario=self.origen, rut="1-9", nombres="A", apellidos="A",
                               correo_institucional=CLOUD, activo=True)
        Docente.objects.create(usuario=self.destino, rut="2-7", nombres="B", apellidos="B",
                               correo_institucional=UA, activo=True)
        solicitud = self.crear_solicitud(self.origen)

        with self.assertRaisesMessage(services.IdentidadError, "coordinación"):
            services.fusionar_usuarios(self.origen, self.destino)

        solicitud.refresh_from_db()
        self.origen.refresh_from_db()
        self.assertEqual(solicitud.solicitante_usuario, self.origen)
        self.assertTrue(self.origen.is_active)


class MigracionTests(TestCase):
    def test_crea_una_identidad_principal_por_usuario_con_correo(self):
        con_oid = Usuario.objects.create_user(username="a", correo_institucional="A@uautonoma.cl", entra_oid="oid-real")
        solo_email = Usuario.objects.create_user(username="b", email="b@cloud.uautonoma.cl")
        Usuario.objects.create_user(username="sin-correo")

        self.assertEqual(services.crear_identidades_iniciales(), 2)
        self.assertEqual(services.crear_identidades_iniciales(), 0, "se puede repetir sin duplicar")

        a = con_oid.identidades.get()
        self.assertEqual((a.correo, a.entra_oid, a.es_principal, a.origen_vinculo),
                         ("a@uautonoma.cl", "oid-real", True, "INICIAL"))
        b = solo_email.identidades.get()
        self.assertTrue(b.entra_oid.startswith("sim-"))
        self.assertEqual(b.tenant_id, "simulado")


@override_settings(ENTRA_MODO="simulado", ENTRA_DOMINIO_PERMITIDO=None, ENTRA_DOMINIOS_PERMITIDOS=None)
class SesionEnRegistrosTests(BaseIdentidades):
    """Informante y solicitante guardan la cuenta usada en ESTA sesión."""

    def setUp(self):
        sede = Sede.objects.create(nombre="Sede", activo=True)
        campus = Campus.objects.create(sede=sede, nombre="Campus", activo=True)
        self.seccion = Seccion.objects.create(
            periodo=PeriodoAcademico.objects.create(anio=2026, nombre="2026"), campus=campus,
            asignatura=Asignatura.objects.create(codigo="AS1", nombre="Taller", activo=True),
            nrc="888", seccion="1", estado="ACTIVA",
        )
        self.docente = Docente.objects.create(
            rut="11111111-1", nombres="D", apellidos="P", correo_institucional="profe@uautonoma.cl", activo=True,
        )
        # El estudiante tiene sus dos cuentas; la principal es la @uautonoma.cl.
        self.ingresar("ana@uautonoma.cl")
        self.vincular("ana@cloud.uautonoma.cl")
        self.client.logout()
        self.ingresar("ana@cloud.uautonoma.cl")

    def test_informante_del_equipo(self):
        enlace = EnlaceRegistroEquipo.objects.create(
            seccion=self.seccion, creado_por_docente=self.docente, fecha_inicio=timezone.now(),
            fecha_expiracion=timezone.now() + timedelta(days=1), activo=True,
        )
        url = reverse("proyectos:acceso_registro_equipos", kwargs={"token": enlace.token})
        self.assertContains(self.client.get(url), "ana@cloud.uautonoma.cl")
        datos = {
            "clave_idempotencia": str(uuid.uuid4()), "tipo_socio": "provisional",
            "socio_provisional_nombre": "Org", "cantidad_integrantes": "1",
            "rut_1": "12.345.678-5", "nombres_1": "Ana", "apellidos_1": "Pérez",
            "correo_1": "ana@cloud.uautonoma.cl",
        }
        self.client.post(url, datos)
        equipo = Equipo.objects.get()
        self.assertEqual(equipo.informante_correo, "ana@cloud.uautonoma.cl")
        self.assertEqual(
            equipo.informante_entra_id,
            IdentidadInstitucional.objects.get(correo="ana@cloud.uautonoma.cl").entra_oid,
        )

        # Con la otra cuenta no puede registrar un segundo equipo en la sección.
        self.client.logout()
        self.ingresar("ana@uautonoma.cl")
        datos.update(clave_idempotencia=str(uuid.uuid4()), correo_1="ana@uautonoma.cl")
        respuesta = self.client.post(url, datos)
        self.assertContains(respuesta, "Ya registraste un equipo en esta sección")
        self.assertEqual(Equipo.objects.count(), 1)

    def test_solicitante_de_carta(self):
        enlace = EnlaceSolicitudCarta.objects.create(
            seccion=self.seccion, creado_por_docente=self.docente, fecha_inicio=timezone.now(), activo=True,
        )
        self.client.post(
            reverse("cartas:solicitar_carta_estudiante", kwargs={"token": enlace.token}),
            {"institucion_receptora": "Junta de vecinos", "persona_receptora": "Presidenta"},
        )
        solicitud = SolicitudCarta.objects.get()
        self.assertEqual(solicitud.solicitante_correo, "ana@cloud.uautonoma.cl")
        self.assertEqual(solicitud.solicitante_entra_id,
                         IdentidadInstitucional.objects.get(correo="ana@cloud.uautonoma.cl").entra_oid)


@override_settings(ENTRA_MODO="simulado", ENTRA_DOMINIO_PERMITIDO=None, ENTRA_DOMINIOS_PERMITIDOS=None)
class AvisoVincularTests(BaseIdentidades):
    TEXTO = "¿También tienes una cuenta @cloud.uautonoma.cl?"

    def test_docente_con_un_dominio_ve_el_aviso_y_puede_ocultarlo(self):
        self.ingresar(UA)
        url = reverse("core:inicio_docente")
        self.assertContains(self.client.get(url), self.TEXTO)
        self.client.post(reverse("usuarios:ocultar_aviso_vincular"), {"next": url})
        self.assertNotContains(self.client.get(url), self.TEXTO)

    def test_aviso_inverso_para_quien_entra_con_cloud(self):
        self.ingresar(CLOUD)
        self.assertContains(
            self.client.get(reverse("core:inicio_docente")),
            "¿También tienes una cuenta @uautonoma.cl?",
        )

    def test_coordinador_ve_el_aviso(self):
        self.ingresar("coordinador@uautonoma.cl")
        self.assertContains(self.client.get(reverse("core:coordinacion")), self.TEXTO)

    def test_con_los_dos_dominios_no_hay_aviso(self):
        self.ingresar(UA)
        self.vincular(CLOUD)
        self.assertNotContains(self.client.get(reverse("core:inicio_docente")), "¿También tienes")

    def test_estudiante_y_paginas_publicas_no_ven_el_aviso(self):
        self.assertNotContains(self.client.get(reverse("core:inicio")), "¿También tienes")
        self.ingresar("estudiante@uautonoma.cl")
        self.assertNotContains(self.client.get(reverse("core:inicio")), "¿También tienes")
        self.assertIsNone(
            services.aviso_vincular_cuenta(type("R", (), {"user": self.usuario_en_sesion(), "session": {}})())
        )
