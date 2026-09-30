from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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


# Pendientes (necesitan los modelos de academico, proyectos y encuestas):
#  - filtros por sede, campus, carrera, período y año vía ParticipacionSocio
#  - historial cronológico ordenado de participaciones
#  - revisión de postulaciones (aprobar, rechazar con y sin motivo)