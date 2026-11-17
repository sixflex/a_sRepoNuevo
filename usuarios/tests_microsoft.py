"""
Ingreso real con Microsoft (ENTRA_MODO=microsoft) y acceso de respaldo.

msal se reemplaza por un doble: las pruebas no salen a internet. Lo que se
prueba es lo nuestro: a dónde se manda a la persona, qué se acepta de lo que
devuelve Microsoft y qué rol le da el portal.
"""
from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from academico.models import Docente

from . import entra


Usuario = get_user_model()
TENANT = "11111111-2222-3333-4444-555555555555"

CONFIG = dict(
    ENTRA_MODO="microsoft",
    ENTRA_TENANT_ID=TENANT,
    ENTRA_CLIENT_ID="app-id",
    ENTRA_CLIENT_SECRET="secreto",
    ENTRA_REDIRECT_URI="",
    ENTRA_DOMINIO_PERMITIDO="",
    ENTRA_DOMINIOS_PERMITIDOS="uautonoma.cl,cloud.uautonoma.cl",
    COORDINADORES="jreino@uautonoma.cl",
)


def _claims(correo, oid="oid-1", tid=TENANT, **extra):
    return {"tid": tid, "oid": oid, "preferred_username": correo,
            "given_name": "Jorge", "family_name": "Reino", **extra}


@override_settings(**CONFIG)
class IngresoMicrosoftTests(TestCase):
    def setUp(self):
        self.msal = MagicMock()
        self.app = self.msal.ConfidentialClientApplication.return_value
        self.app.initiate_auth_code_flow.return_value = {
            "auth_uri": "https://login.microsoftonline.com/x/authorize?state=abc",
            "state": "abc",
        }
        parche = patch.dict("sys.modules", {"msal": self.msal})
        parche.start()
        self.addCleanup(parche.stop)

    def ir_a_microsoft(self, **params):
        return self.client.get(reverse("usuarios:entra_login"), params)

    def volver_de_microsoft(self, claims=None, resultado=None):
        self.ir_a_microsoft()
        self.app.acquire_token_by_auth_code_flow.return_value = (
            resultado if resultado is not None else {"id_token_claims": claims}
        )
        return self.client.get(reverse("usuarios:entra_callback"), {"code": "c", "state": "abc"})

    def usuario_en_sesion(self):
        return Usuario.objects.get(pk=self.client.session["_auth_user_id"])

    # --- pantalla de login ----------------------------------------------------

    def test_login_muestra_microsoft_y_deja_la_clave_como_respaldo(self):
        respuesta = self.client.get(reverse("usuarios:login"))
        self.assertContains(respuesta, "Iniciar sesión con Microsoft")
        self.assertContains(respuesta, "Acceso de respaldo")
        self.assertNotContains(respuesta, "acceso simulado")

    def test_boton_manda_a_microsoft_con_la_url_de_vuelta(self):
        respuesta = self.ir_a_microsoft()
        self.assertRedirects(respuesta, "https://login.microsoftonline.com/x/authorize?state=abc",
                             fetch_redirect_response=False)
        args, kwargs = self.app.initiate_auth_code_flow.call_args
        self.assertEqual(kwargs["redirect_uri"], "http://testserver/usuarios/auth/callback/")
        self.assertEqual(kwargs["prompt"], "select_account")  # siempre se elige la cuenta
        _, opciones = self.msal.ConfidentialClientApplication.call_args
        self.assertEqual(opciones["authority"], f"https://login.microsoftonline.com/{TENANT}")
        self.assertEqual(opciones["client_credential"], "secreto")

    @override_settings(ENTRA_CLIENT_SECRET="")
    def test_sin_credenciales_avisa_y_no_rompe(self):
        respuesta = self.ir_a_microsoft()
        self.assertEqual(respuesta.status_code, 400)
        self.assertContains(respuesta, "ENTRA_CLIENT_SECRET", status_code=400)
        self.assertContains(respuesta, "respaldo", status_code=400)

    # --- roles ---------------------------------------------------------------

    def test_coordinador_de_la_lista_entra_a_su_panel(self):
        respuesta = self.volver_de_microsoft(_claims("JReino@uautonoma.cl"))
        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)
        usuario = self.usuario_en_sesion()
        self.assertEqual(usuario.rol.nombre, "Coordinador")
        self.assertTrue(usuario.groups.filter(name="Coordinador").exists())
        self.assertFalse(usuario.groups.filter(name="Estudiante").exists())
        self.assertEqual(usuario.identidades.get().tenant_id, TENANT)

    def test_docente_registrado_queda_enlazado(self):
        docente = Docente.objects.create(nombres="Ana", apellidos="Pérez",
                                         correo_institucional="ana.perez@uautonoma.cl", activo=True)
        respuesta = self.volver_de_microsoft(_claims("ana.perez@uautonoma.cl", oid="oid-ana"))
        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)
        docente.refresh_from_db()
        self.assertEqual(docente.usuario, self.usuario_en_sesion())
        self.assertEqual(docente.usuario.rol.nombre, "Docente")

    def test_cuenta_de_la_u_sin_rol_no_ve_paneles(self):
        respuesta = self.volver_de_microsoft(_claims("alumno@cloud.uautonoma.cl", oid="oid-al"))
        self.assertRedirects(respuesta, reverse("usuarios:sin_panel"), fetch_redirect_response=False)
        self.assertEqual(self.usuario_en_sesion().rol.nombre, "Estudiante")
        self.assertContains(self.client.get(reverse("usuarios:sin_panel")), "no tiene un panel")
        self.assertNotEqual(self.client.get(reverse("core:coordinacion")).status_code, 200)

    def test_coordinador_existente_con_clave_entra_con_microsoft_a_la_misma_cuenta(self):
        call_command("crear_coordinador", "jreino@uautonoma.cl", stdout=StringIO())
        antes = Usuario.objects.get()
        self.volver_de_microsoft(_claims("jreino@uautonoma.cl", oid="oid-real"))
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(self.usuario_en_sesion().pk, antes.pk)

    def test_vuelve_a_la_pagina_que_pidio(self):
        self.ir_a_microsoft(next="/cartas/")
        self.app.acquire_token_by_auth_code_flow.return_value = {
            "id_token_claims": _claims("jreino@uautonoma.cl")}
        respuesta = self.client.get(reverse("usuarios:entra_callback"), {"code": "c", "state": "abc"})
        self.assertRedirects(respuesta, "/cartas/", fetch_redirect_response=False)

    # --- lo que no se acepta -----------------------------------------------------

    def comprobar_rechazo(self, respuesta, texto):
        self.assertContains(respuesta, texto, status_code=400)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(ENTRA_TENANT_ID=f"{TENANT}, 99999999-0000-0000-0000-000000000000")
    def test_dos_tenants_de_la_u_usan_organizations_y_aceptan_ambos(self):
        respuesta = self.volver_de_microsoft(
            _claims("alumno@cloud.uautonoma.cl", tid="99999999-0000-0000-0000-000000000000"))
        self.assertEqual(respuesta.status_code, 302)
        _, opciones = self.msal.ConfidentialClientApplication.call_args
        self.assertEqual(opciones["authority"], "https://login.microsoftonline.com/organizations")
        self.assertIn("_auth_user_id", self.client.session)

    def test_cuenta_de_otro_tenant_no_entra(self):
        self.comprobar_rechazo(
            self.volver_de_microsoft(_claims("jreino@uautonoma.cl", tid="otro-tenant")),
            "Solo se aceptan cuentas",
        )
        self.assertEqual(Usuario.objects.count(), 0)

    def test_correo_de_otro_dominio_no_entra(self):
        self.comprobar_rechazo(self.volver_de_microsoft(_claims("persona@gmail.com")), "institucionales")
        self.assertEqual(Usuario.objects.count(), 0)

    def test_microsoft_rechaza_por_falta_de_consentimiento(self):
        respuesta = self.volver_de_microsoft(resultado={
            "error": "invalid_grant",
            "error_description": "AADSTS65001: The user or administrator has not consented.",
        })
        self.comprobar_rechazo(respuesta, "consentimiento")

    def test_respuesta_alterada_o_vencida(self):
        self.ir_a_microsoft()
        self.app.acquire_token_by_auth_code_flow.side_effect = ValueError("state mismatch")
        respuesta = self.client.get(reverse("usuarios:entra_callback"), {"code": "c", "state": "otro"})
        self.comprobar_rechazo(respuesta, "venció")

    def test_volver_sin_haber_pasado_por_el_boton(self):
        respuesta = self.client.get(reverse("usuarios:entra_callback"), {"code": "c", "state": "abc"})
        self.comprobar_rechazo(respuesta, "venció")

    def test_cuenta_desactivada_no_entra(self):
        call_command("crear_coordinador", "jreino@uautonoma.cl", stdout=StringIO())
        Usuario.objects.update(is_active=False)
        self.comprobar_rechazo(self.volver_de_microsoft(_claims("jreino@uautonoma.cl")), "desactivada")

    @override_settings(ENTRA_MODO="desactivado")
    def test_callback_no_existe_si_microsoft_no_esta_activo(self):
        self.assertEqual(self.client.get(reverse("usuarios:entra_callback")).status_code, 404)


@override_settings(**CONFIG)
class AccesoDeRespaldoTests(TestCase):
    """El portal nunca queda sin quién lo administre, aunque Microsoft falle."""

    def test_crear_coordinador_con_clave_y_entrar_sin_microsoft(self):
        with patch("getpass.getpass", side_effect=["Clave-Segura-2026", "Clave-Segura-2026"]):
            call_command("crear_coordinador", "jreino@uautonoma.cl", "--clave", "--nombre", "Jorge",
                         stdout=StringIO())
        usuario = Usuario.objects.get()
        self.assertEqual(usuario.rol.nombre, "Coordinador")
        self.assertTrue(usuario.groups.filter(name="Coordinador").exists())
        self.assertTrue(self.client.login(username="jreino@uautonoma.cl", password="Clave-Segura-2026"))

    def test_claves_distintas_no_se_guardan(self):
        with patch("getpass.getpass", side_effect=["una", "otra"]):
            with self.assertRaises(CommandError):
                call_command("crear_coordinador", "jreino@uautonoma.cl", "--clave", stdout=StringIO())

    def test_correo_de_otro_dominio_no_se_acepta(self):
        with self.assertRaises(CommandError):
            call_command("crear_coordinador", "jorge@gmail.com", stdout=StringIO())

    def test_usuario_existente_pasa_a_coordinador_sin_duplicarse(self):
        Group.objects.get_or_create(name="Estudiante")
        call_command("crear_coordinador", "jreino@uautonoma.cl", stdout=StringIO())
        call_command("crear_coordinador", "jreino@uautonoma.cl", stdout=StringIO())
        self.assertEqual(Usuario.objects.count(), 1)


class ConfiguracionMicrosoftTests(TestCase):
    @override_settings(ENTRA_TENANT_ID="", ENTRA_CLIENT_ID="", ENTRA_CLIENT_SECRET="")
    def test_dice_que_falta(self):
        with self.assertRaisesMessage(entra.EntraError, "ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET"):
            entra.configuracion_microsoft()

    @override_settings(COORDINADORES=" JReino@uautonoma.cl , otra@uautonoma.cl,")
    def test_lista_de_coordinadores(self):
        self.assertEqual(entra.correos_coordinadores(), {"jreino@uautonoma.cl", "otra@uautonoma.cl"})
