"""SP5-T02 / CDE-538: acceso simulado con Microsoft, por rol y dominio."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .entra import CUENTAS_PRUEBA


Usuario = get_user_model()


@override_settings(ENTRA_MODO="simulado", ENTRA_DOMINIO_PERMITIDO="uautonoma.cl")
class AccesoSimuladoTests(TestCase):
    def setUp(self):
        self.url = reverse("usuarios:entra_login")

    def ingresar(self, correo, **extra):
        return self.client.post(self.url, {"correo": correo, **extra})

    def sesion_iniciada(self):
        return "_auth_user_id" in self.client.session

    # --- pantalla y botón ---------------------------------------------------

    def test_login_muestra_boton_de_microsoft(self):
        respuesta = self.client.get(reverse("usuarios:login"))
        self.assertContains(respuesta, "Iniciar sesión con Microsoft")
        self.assertContains(respuesta, self.url)

    def test_pantalla_simulada_lista_cuentas_de_prueba(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Simulación")
        self.assertContains(respuesta, "Iniciar sesión")
        for cuenta in CUENTAS_PRUEBA:
            self.assertContains(respuesta, cuenta["correo"])

    # --- acceso por rol -----------------------------------------------------

    def comprobar_acceso(self, correo, rol):
        respuesta = self.ingresar(correo)
        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)
        self.assertTrue(self.sesion_iniciada())

        usuario = Usuario.objects.get(correo_institucional=correo)
        self.assertEqual(usuario.rol.nombre, rol)
        self.assertEqual(list(usuario.groups.values_list("name", flat=True)), [rol])
        self.assertTrue(usuario.entra_oid.startswith("sim-"))
        self.assertIsNotNone(usuario.fecha_ultimo_acceso)
        self.assertFalse(usuario.has_usable_password())

    def test_coordinador_entra_con_cuenta_simulada(self):
        self.comprobar_acceso("coordinador@uautonoma.cl", "Coordinador")

    def test_docente_entra_con_cuenta_simulada(self):
        self.comprobar_acceso("docente@uautonoma.cl", "Docente")

    def test_estudiante_entra_con_cuenta_simulada(self):
        self.comprobar_acceso("estudiante@uautonoma.cl", "Estudiante")

    def test_correo_institucional_sin_rol_conocido_entra_como_estudiante(self):
        self.comprobar_acceso("ana.perez@uautonoma.cl", "Estudiante")

    def test_correo_se_normaliza_a_minusculas(self):
        self.ingresar("  Docente@UAutonoma.CL ")
        self.assertTrue(self.sesion_iniciada())
        self.assertEqual(Usuario.objects.filter(correo_institucional="docente@uautonoma.cl").count(), 1)

    # --- dominio ------------------------------------------------------------

    def test_otro_dominio_es_rechazado(self):
        respuesta = self.ingresar("alguien@gmail.com")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Solo se permiten cuentas institucionales")
        self.assertFalse(self.sesion_iniciada())
        self.assertFalse(Usuario.objects.filter(correo_institucional="alguien@gmail.com").exists())

    def test_dominios_parecidos_son_rechazados(self):
        for correo in (
            "x@uautonoma.cl.evil.com",
            "x@evil-uautonoma.cl",
            "x@mail.uautonoma.cl",
            "x@uautonoma.com",
        ):
            with self.subTest(correo=correo):
                self.ingresar(correo)
                self.assertFalse(self.sesion_iniciada())
                self.assertFalse(Usuario.objects.filter(correo_institucional=correo).exists())

    def test_correo_vacio_o_mal_formado_es_rechazado(self):
        for correo in ("", "   ", "sin-arroba", "a@b", "@uautonoma.cl"):
            with self.subTest(correo=correo):
                respuesta = self.ingresar(correo)
                self.assertContains(respuesta, "correo válido")
                self.assertFalse(self.sesion_iniciada())

    # --- entra_oid y usuarios existentes -----------------------------------

    def test_segundo_acceso_reutiliza_el_mismo_usuario_y_oid(self):
        self.ingresar("docente@uautonoma.cl")
        primer_oid = Usuario.objects.get().entra_oid
        self.client.logout()
        self.ingresar("docente@uautonoma.cl")
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(Usuario.objects.get().entra_oid, primer_oid)

    def test_usuario_existente_conserva_su_rol_y_grupo(self):
        from django.contrib.auth.models import Group
        from .models import Rol

        rol = Rol.objects.create(nombre="Coordinador")
        existente = Usuario.objects.create_user(
            username="docente@uautonoma.cl", correo_institucional="docente@uautonoma.cl", rol=rol
        )
        existente.groups.add(Group.objects.create(name="Coordinador"))

        self.ingresar("docente@uautonoma.cl")

        existente.refresh_from_db()
        self.assertEqual(existente.rol.nombre, "Coordinador")
        self.assertEqual(list(existente.groups.values_list("name", flat=True)), ["Coordinador"])
        self.assertTrue(existente.entra_oid)

    def test_usuario_desactivado_no_puede_entrar(self):
        Usuario.objects.create_user(
            username="docente@uautonoma.cl", correo_institucional="docente@uautonoma.cl", activo=False
        )
        respuesta = self.ingresar("docente@uautonoma.cl")
        self.assertContains(respuesta, "desactivada")
        self.assertFalse(self.sesion_iniciada())

    # --- cambio de cuenta ---------------------------------------------------

    def test_con_sesion_iniciada_se_puede_ver_el_login_y_cambiar_de_cuenta(self):
        self.ingresar("estudiante@uautonoma.cl")
        self.assertEqual(self.client.get(reverse("usuarios:login")).status_code, 200)

        self.ingresar("coordinador@uautonoma.cl")
        usuario_en_sesion = int(self.client.session["_auth_user_id"])
        self.assertEqual(
            Usuario.objects.get(pk=usuario_en_sesion).correo_institucional,
            "coordinador@uautonoma.cl",
        )

    def test_login_avisa_que_ya_hay_una_sesion(self):
        self.ingresar("estudiante@uautonoma.cl")
        respuesta = self.client.get(reverse("usuarios:login"))
        self.assertContains(respuesta, "Tienes la sesión iniciada como")

    # --- redirección --------------------------------------------------------

    def test_respeta_next_interno(self):
        respuesta = self.ingresar("docente@uautonoma.cl", next="/socios/catalogo/")
        self.assertRedirects(respuesta, "/socios/catalogo/", fetch_redirect_response=False)

    def test_ignora_next_externo(self):
        respuesta = self.ingresar("docente@uautonoma.cl", next="https://evil.com/")
        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)


class AccesoSimuladoDesactivadoTests(TestCase):
    @override_settings(ENTRA_MODO="desactivado")
    def test_pantalla_y_boton_no_existen_si_esta_desactivado(self):
        self.assertEqual(self.client.get(reverse("usuarios:entra_login")).status_code, 404)
        self.assertEqual(
            self.client.post(reverse("usuarios:entra_login"), {"correo": "docente@uautonoma.cl"}).status_code,
            404,
        )
        self.assertNotContains(self.client.get(reverse("usuarios:login")), "Iniciar sesión con Microsoft")
        self.assertEqual(Usuario.objects.count(), 0)

    @override_settings(DEBUG=False)
    def test_por_defecto_esta_desactivado_fuera_de_debug(self):
        self.assertEqual(self.client.get(reverse("usuarios:entra_login")).status_code, 404)
