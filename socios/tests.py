from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comunicaciones.models import EnvioCorreo
from encuestas.models import FormularioPlantilla, FormularioVersion, RespuestaFormulario
from socios.models import Convocatoria, PostulacionSocio, SocioComunitario
from socios.validators import validar_rut_chileno

from .models import (
    ClasificacionSocio,
    Comuna,
    ContactoSocio,
    SocioComunitario,
)

User = get_user_model()


def crear_usuario(nombre_grupo):
    """Crea un usuario dentro del grupo indicado (Coordinador o Docente)."""
    user = User.objects.create_user(username=nombre_grupo.lower(), password="clave-de-prueba")
    grupo, _ = Group.objects.get_or_create(name=nombre_grupo)
    user.groups.add(grupo)
    return user


def crear_socio(nombre, **kwargs):
    """Crea un socio con los campos obligatorios del modelo."""
    datos = {
        "nombre_organizacion": nombre,
        "estado_revision": "APROBADO",
        "es_provisional": False,
        "activo": True,
        "fecha_creacion": timezone.now(),
    }
    datos.update(kwargs)
    return SocioComunitario.objects.create(**datos)


def nombres(response):
    return {s.nombre_organizacion for s in response.context["socios"]}


class DatosBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.coordinador = crear_usuario("Coordinador")
        cls.docente = crear_usuario("Docente")

        cls.clasif_fundacion = ClasificacionSocio.objects.create(nombre="Fundación", activo=True)
        cls.clasif_junta = ClasificacionSocio.objects.create(nombre="Junta de vecinos", activo=True)
        cls.comuna_a = Comuna.objects.create(nombre="Providencia", region="RM", activo=True)
        cls.comuna_b = Comuna.objects.create(nombre="Maipú", region="RM", activo=True)

        cls.esperanza = crear_socio(
            "Fundación Esperanza", rut="76.123.456-7",
            clasificacion=cls.clasif_fundacion, comuna=cls.comuna_a,
            estado_revision="APROBADO",
        )
        cls.norte = crear_socio(
            "Junta Norte", rut="65.987.654-3",
            clasificacion=cls.clasif_junta, comuna=cls.comuna_b,
            estado_revision="RECIBIDO", es_provisional=True,
        )
        cls.rechazado = crear_socio(
            "Club Rechazado", rut="70.111.222-3", estado_revision="RECHAZADO",
        )
        cls.disponible = crear_socio(
            "Centro Disponible", rut="71.222.333-4", estado_revision="DISPONIBLE",
        )
        cls.terminado = crear_socio(
            "Taller Terminado", rut="72.333.444-5", estado_revision="TRABAJO_TERMINADO",
        )
        cls.inactivo = crear_socio(
            "Grupo Inactivo", rut="73.444.555-6", estado_revision="APROBADO", activo=False,
        )

        ContactoSocio.objects.create(
            socio=cls.esperanza, nombre="María Contreras",
            es_principal=True, activo=True,
        )


class BusquedaCoordinadorTests(DatosBase):
    """CDE-62: búsqueda por nombre, RUT, organización, clasificación y comuna."""

    def setUp(self):
        self.client.force_login(self.coordinador)
        self.url = reverse("socios:lista_coordinador")

    def test_sin_filtros_lista_todos(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(nombres(resp)), 6)

    def test_busqueda_por_nombre_de_organizacion(self):
        resp = self.client.get(self.url, {"q": "esperanza"})
        self.assertEqual(nombres(resp), {"Fundación Esperanza"})

    def test_busqueda_por_rut(self):
        resp = self.client.get(self.url, {"q": "65.987.654-3"})
        self.assertEqual(nombres(resp), {"Junta Norte"})

    def test_busqueda_por_nombre_de_contacto(self):
        resp = self.client.get(self.url, {"q": "Contreras"})
        self.assertEqual(nombres(resp), {"Fundación Esperanza"})

    def test_busqueda_sin_resultados(self):
        resp = self.client.get(self.url, {"q": "no-existe-xyz"})
        self.assertEqual(nombres(resp), set())

    def test_filtro_por_clasificacion(self):
        resp = self.client.get(self.url, {"clasificacion": self.clasif_junta.id})
        self.assertEqual(nombres(resp), {"Junta Norte"})

    def test_filtro_por_comuna(self):
        resp = self.client.get(self.url, {"comuna": self.comuna_a.id})
        self.assertEqual(nombres(resp), {"Fundación Esperanza"})


class FiltrosCombinadosTests(DatosBase):
    """CDE-63 y CDE-65: filtros por estado, tipo de registro y disponibilidad."""

    def setUp(self):
        self.client.force_login(self.coordinador)
        self.url = reverse("socios:lista_coordinador")

    def test_filtro_por_estado(self):
        resp = self.client.get(self.url, {"estado": "RECHAZADO"})
        self.assertEqual(nombres(resp), {"Club Rechazado"})

    def test_filtro_provisional(self):
        resp = self.client.get(self.url, {"provisional": "1"})
        self.assertEqual(nombres(resp), {"Junta Norte"})

    def test_filtro_definitivo(self):
        resp = self.client.get(self.url, {"provisional": "0"})
        self.assertNotIn("Junta Norte", nombres(resp))
        self.assertIn("Fundación Esperanza", nombres(resp))

    def test_filtros_combinados(self):
        resp = self.client.get(
            self.url, {"estado": "RECIBIDO", "provisional": "1", "comuna": self.comuna_b.id}
        )
        self.assertEqual(nombres(resp), {"Junta Norte"})

    def test_filtros_combinados_sin_coincidencia(self):
        resp = self.client.get(self.url, {"estado": "APROBADO", "provisional": "1"})
        self.assertEqual(nombres(resp), set())

    def test_vista_disponibles(self):
        resp = self.client.get(self.url, {"vista": "disponibles"})
        self.assertEqual(nombres(resp), {"Fundación Esperanza", "Centro Disponible"})

    def test_vista_solo_historial(self):
        resp = self.client.get(self.url, {"vista": "historial"})
        self.assertEqual(nombres(resp), {"Taller Terminado", "Grupo Inactivo"})


class CatalogoDocenteTests(DatosBase):
    """CDE-60: el catálogo solo muestra socios aprobados o disponibles."""

    def setUp(self):
        self.client.force_login(self.docente)
        self.url = reverse("socios:catalogo_docente")

    def test_muestra_aprobados_y_disponibles(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(nombres(resp), {"Fundación Esperanza", "Centro Disponible"})

    def test_excluye_provisionales_rechazados_terminados_e_inactivos(self):
        resp = self.client.get(self.url)
        excluidos = {"Junta Norte", "Club Rechazado", "Taller Terminado", "Grupo Inactivo"}
        self.assertTrue(excluidos.isdisjoint(nombres(resp)))

    def test_busqueda_en_catalogo(self):
        resp = self.client.get(self.url, {"q": "Disponible"})
        self.assertEqual(nombres(resp), {"Centro Disponible"})


class CambioEstadoTests(DatosBase):
    """CDE-59: cambios de estado de socios."""

    def setUp(self):
        self.client.force_login(self.coordinador)

    def url_cambio(self, socio):
        return reverse("socios:cambiar_estado", args=[socio.id])

    def test_cambio_de_estado_se_guarda(self):
        self.client.post(self.url_cambio(self.norte), {"estado_revision": "APROBADO"})
        self.norte.refresh_from_db()
        self.assertEqual(self.norte.estado_revision, "APROBADO")
        self.assertFalse(self.norte.es_provisional)

    def test_se_puede_mantener_provisional(self):
        self.client.post(
            self.url_cambio(self.norte),
            {"estado_revision": "APROBADO", "es_provisional": "1"},
        )
        self.norte.refresh_from_db()
        self.assertTrue(self.norte.es_provisional)

    def test_estado_invalido_se_ignora(self):
        self.client.post(self.url_cambio(self.esperanza), {"estado_revision": "INVENTADO"})
        self.esperanza.refresh_from_db()
        self.assertEqual(self.esperanza.estado_revision, "APROBADO")

    def test_get_no_modifica_el_socio(self):
        self.client.get(self.url_cambio(self.norte))
        self.norte.refresh_from_db()
        self.assertEqual(self.norte.estado_revision, "RECIBIDO")

    def test_ficha_del_socio_carga(self):
        resp = self.client.get(reverse("socios:detalle_historial", args=[self.norte.id]))
        self.assertEqual(resp.status_code, 200)


class PermisosTests(DatosBase):
    def test_docente_no_accede_al_panel_del_coordinador(self):
        self.client.force_login(self.docente)
        resp = self.client.get(reverse("socios:lista_coordinador"))
        self.assertNotEqual(resp.status_code, 200)

    def test_coordinador_no_accede_al_catalogo_docente(self):
        self.client.force_login(self.coordinador)
        resp = self.client.get(reverse("socios:catalogo_docente"))
        self.assertNotEqual(resp.status_code, 200)

    def test_anonimo_no_accede(self):
        resp = self.client.get(reverse("socios:lista_coordinador"))
        self.assertNotEqual(resp.status_code, 200)

class PostulacionSocioPublicaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.coordinador = User.objects.create_user(
            username="coord_test",
            password="test-password-123",
        )
        grupo_coord, _ = Group.objects.get_or_create(name="Coordinador")
        self.coordinador.groups.add(grupo_coord)

        self.plantilla = FormularioPlantilla.objects.create(
            codigo="POST-SOCIO-V1",
            titulo="Formulario de Postulación de Socios",
            proceso="POSTULACION",
            activo=True,
        )
        self.version = FormularioVersion.objects.create(
            plantilla=self.plantilla,
            numero_version=1,
            estado="PUBLICADO",
            fecha_creacion=timezone.now(),
        )

        self.convocatoria_activa = Convocatoria.objects.create(
            formulario_version=self.version,
            nombre="Convocatoria A+S 2026",
            fecha_inicio=timezone.now() - timedelta(days=2),
            fecha_fin=timezone.now() + timedelta(days=15),
            estado="PUBLICADA",
        )

        self.convocatoria_expirada = Convocatoria.objects.create(
            formulario_version=self.version,
            nombre="Convocatoria Antigua Pasada",
            fecha_inicio=timezone.now() - timedelta(days=30),
            fecha_fin=timezone.now() - timedelta(days=5),
            estado="PUBLICADA",
        )

    # CDE-52: Validación de RUT chileno (Módulo 11)
    def test_cde_52_validador_rut_chileno(self):
        # Casos válidos matemáticos reales: numérico, con K y con 0
        self.assertEqual(validar_rut_chileno("11.111.111-1"), "11111111-1")
        self.assertEqual(validar_rut_chileno("11.111.112-k"), "11111112-K")
        self.assertEqual(validar_rut_chileno("60.805.000-0"), "60805000-0")

        # Casos inválidos
        with self.assertRaises(ValidationError):
            validar_rut_chileno("11.111.111-9")
        with self.assertRaises(ValidationError):
            validar_rut_chileno("invalido")
        with self.assertRaises(ValidationError):
            validar_rut_chileno("")

    # CDE-49 / CDE-50: Formulario público y aviso de cierre
    def test_cde_50_convocatoria_expirada_muestra_aviso_cierre(self):
        url = reverse("socios:postular_convocatoria", args=[self.convocatoria_expirada.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ha cerrado su período de postulación")

    # CDE-49, CDE-51, CDE-52, CDE-53, CDE-56: Postulación válida y confirmación
    def test_cde_53_postulacion_exitosa_crea_folio_y_auditoria_correo(self):
        url = reverse("socios:postular_convocatoria", args=[self.convocatoria_activa.id])
        data = {
            "nombre_organizacion": "Junta de Vecinos San Joaquín",
            "rut": "11.111.111-1",
            "contacto_nombre": "Marta Gómez",
            "correo": "marta.gomez@vecinos.cl",
            "telefono": "+56911223344",
            "linea_servicio": "TECNOLOGIA",
            "detalle_adicional": "Requerimos capacitación en ofimática.",
        }
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)

        postulacion = PostulacionSocio.objects.filter(
            respuesta_formulario__respondente_rut="11111111-1"
        ).first()
        self.assertIsNotNone(postulacion)
        self.assertEqual(postulacion.estado, "RECIBIDA")
        self.assertEqual(postulacion.socio.nombre_organizacion, "Junta de Vecinos San Joaquín")
        self.assertTrue(postulacion.socio.es_provisional)

        self.assertContains(response, f"#{postulacion.id}")
        self.assertContains(response, "¡Postulación Recibida con Éxito!")

        registro_correo = EnvioCorreo.objects.filter(postulacion=postulacion).first()
        self.assertIsNotNone(registro_correo)
        self.assertEqual(registro_correo.destinatario, "marta.gomez@vecinos.cl")
        self.assertEqual(registro_correo.resultado, "OK")

    # CDE-52: Bloqueo de postulaciones duplicadas
    def test_cde_52_bloquea_postulacion_duplicada_mismo_rut(self):
        url = reverse("socios:postular_convocatoria", args=[self.convocatoria_activa.id])
        data = {
            "nombre_organizacion": "Fundación Esperanza",
            "rut": "11.111.111-1",
            "contacto_nombre": "Carlos Rojas",
            "correo": "carlos@fundacion.cl",
            "linea_servicio": "SALUD",
        }
        # Primer envío
        self.client.post(url, data)

        # Segundo envío con mismo RUT
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe una postulación registrada para el RUT 11111111-1")

    # CDE-54, CDE-55, CDE-56: Revisión, motivo de rechazo y auditoría
    def test_cde_54_y_55_revision_postulacion_coordinador(self):
        socio = SocioComunitario.objects.create(
            nombre_organizacion="Club Adulto Mayor",
            rut="76123456-7",
            estado_revision="RECIBIDO",
            es_provisional=True,
            activo=True,
            fecha_creacion=timezone.now(),
        )
        resp = RespuestaFormulario.objects.create(
            version=self.version,
            fecha_envio=timezone.now(),
            origen="PUBLICO",
            es_historica=False,
            respondente_correo="adultos@mayor.cl",
            respondente_rut="76123456-7",
            estado_registro="COMPLETO",
        )
        postulacion = PostulacionSocio.objects.create(
            convocatoria=self.convocatoria_activa,
            respuesta_formulario=resp,
            socio=socio,
            estado="RECIBIDA",
            fecha_recepcion=timezone.now(),
        )

        self.client.force_login(self.coordinador)
        url_revisar = reverse("socios:revisar_postulacion", args=[postulacion.id])

        # Caso A: Rechazar sin motivo falla
        response_rechazo_vacio = self.client.post(url_revisar, {
            "estado": "RECHAZADA",
            "motivo_rechazo": "",
        }, follow=True)
        postulacion.refresh_from_db()
        self.assertEqual(postulacion.estado, "RECIBIDA")
        self.assertContains(response_rechazo_vacio, "Debes indicar un motivo de rechazo.")

        # Caso B: Rechazar con motivo registra estado y auditoría
        response_rechazo_ok = self.client.post(url_revisar, {
            "estado": "RECHAZADA",
            "motivo_rechazo": "Cupos completos para la línea de trabajo.",
        }, follow=True)
        postulacion.refresh_from_db()
        self.assertEqual(postulacion.estado, "RECHAZADA")
        self.assertEqual(postulacion.motivo_rechazo, "Cupos completos para la línea de trabajo.")

        envio_rechazo = EnvioCorreo.objects.filter(postulacion=postulacion, resultado="OK").last()
        self.assertIsNotNone(envio_rechazo)
        self.assertIn("Cupos completos para la línea de trabajo", envio_rechazo.cuerpo)