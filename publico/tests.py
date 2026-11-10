"""
Portal público (HU-10, CDE-20): qué muestra según el Coordinador (RF-PUB-01),
filtro por tipo de socio (CDE-109) y pruebas de privacidad, filtros, datos
agregados, históricos y rendimiento (CDE-114).
"""

import time
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from academico.models import Campus, Carrera, Facultad, PeriodoAcademico, Sede
from auditoria.models import AuditoriaCambio
from core.models import Noticia
from socios.models import ClasificacionSocio, Comuna, ContactoSocio, ParticipacionSocio, SocioComunitario

from .models import ConfiguracionPortal
from .portal import BLOQUES, configuracion_portal


# Datos personales que nunca pueden salir en el portal (RNF-PRI-01).
RUT_SOCIO = "76.543.210-K"
CORREO_SOCIO = "contacto.privado@junta.cl"
TELEFONO_SOCIO = "+56 9 8765 4321"
DIRECCION_SOCIO = "Pasaje Secreto 1234"
NOMBRE_SOCIO = "Junta de Vecinos Los Aromos"


def todas_las_opciones(**cambios):
    """POST de la pantalla con todo encendido; `cambios` apaga bloques u opciones."""
    datos = {}
    for clave, _, _, _, grupos in BLOQUES:
        datos[f"{clave}__activo"] = "on"
        for _, opciones in grupos:
            for opcion, _ in opciones:
                datos[f"{clave}__{opcion}"] = "on"
    for nombre, valor in cambios.items():
        if valor is None:
            datos.pop(nombre, None)
        else:
            datos[nombre] = valor
    return datos


class DatosPortalMixin:
    """Una sede, dos tipos de socio en dos comunas, y una participación histórica."""

    def crear_datos(self):
        self.sede = Sede.objects.create(nombre="Santiago", activo=True)
        self.campus = Campus.objects.create(sede=self.sede, nombre="Providencia", activo=True)
        self.periodo = PeriodoAcademico.objects.create(
            anio=2026, tipo="Semestral", nombre="Primavera 2026 (2º semestre)", estado="Activo",
        )
        facultad = Facultad.objects.create(nombre="Ingeniería", activo=True)
        self.carrera = Carrera.objects.create(facultad=facultad, nombre="Informática", activo=True)

        self.junta = ClasificacionSocio.objects.create(nombre="Junta de vecinos", activo=True)
        self.emprendedor = ClasificacionSocio.objects.create(nombre="Emprendedor", activo=True)
        ClasificacionSocio.objects.create(nombre="Sin participaciones", activo=True)

        self.providencia = Comuna.objects.create(
            nombre="Providencia", region="RM", activo=True, lat_centro=-33.43, lon_centro=-70.61,
        )
        self.maipu = Comuna.objects.create(
            nombre="Maipú", region="RM", activo=True, lat_centro=-33.51, lon_centro=-70.76,
        )

        self.socio_junta = self.socio(NOMBRE_SOCIO, self.junta, self.providencia, rut=RUT_SOCIO,
                                      direccion=DIRECCION_SOCIO)
        ContactoSocio.objects.create(
            socio=self.socio_junta, nombre="Rosa Contacto", correo=CORREO_SOCIO,
            telefono=TELEFONO_SOCIO, es_principal=True, activo=True,
        )
        self.socio_emprendedor = self.socio("Panadería Doña Ana", self.emprendedor, self.maipu)

        # La junta participa dos veces (una del sistema y una histórica de 2024).
        self.participacion(self.socio_junta, servicio="Plan de reciclaje", periodo=self.periodo)
        self.participacion(
            self.socio_junta, servicio="Huerto comunitario", periodo=None,
            fecha_inicio=date(2024, 4, 1), origen="HISTORICO",
        )
        self.participacion(self.socio_emprendedor, servicio="Plan de marketing", periodo=self.periodo)

    def socio(self, nombre, clasificacion, comuna, rut=None, direccion=None):
        return SocioComunitario.objects.create(
            nombre_organizacion=nombre, clasificacion=clasificacion, comuna=comuna, rut=rut,
            direccion_exacta=direccion, estado_revision="APROBADO", es_provisional=False,
            activo=True, fecha_creacion=timezone.now(),
        )

    def participacion(self, socio, servicio, periodo, fecha_inicio=None, origen="OPERATIVO"):
        return ParticipacionSocio.objects.create(
            socio=socio, periodo=periodo, sede=self.sede, campus=self.campus, carrera=self.carrera,
            servicio_realizado=servicio, fecha_inicio=fecha_inicio, origen=origen,
        )

    def inicio(self, **parametros):
        self.client.logout()
        return self.client.get(reverse("core:inicio"), parametros)


class ConfigurarPortalTests(DatosPortalMixin, TestCase):
    """Pestaña "Qué se muestra" (RF-PUB-01): solo Coordinador, valida y audita."""

    def setUp(self):
        User = get_user_model()
        self.coordinador = User.objects.create_user(username="coord_portal", password="x")
        self.coordinador.groups.add(Group.objects.create(name="Coordinador"))
        self.docente = User.objects.create_user(username="doc_portal", password="x")
        self.docente.groups.add(Group.objects.create(name="Docente"))
        self.url = reverse("publico:configurar_portal")

    def test_solo_el_coordinador_entra(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)

        self.client.force_login(self.docente)
        self.assertEqual(self.client.get(self.url).status_code, 403)

        self.client.force_login(self.coordinador)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_sin_configuracion_todo_se_muestra(self):
        portal = configuracion_portal()
        for clave, _, _, _, grupos in BLOQUES:
            self.assertTrue(portal[clave]["activo"], clave)
            for _, opciones in grupos:
                for opcion, _ in opciones:
                    self.assertTrue(portal[clave][opcion], f"{clave}.{opcion}")

    def test_guardar_aplica_y_queda_en_auditoria(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(self.url, todas_las_opciones(
            **{"cifras__facultades": None, "noticias__activo": None}
        ))
        self.assertRedirects(respuesta, self.url)

        portal = configuracion_portal()
        self.assertFalse(portal["cifras"]["facultades"])
        self.assertTrue(portal["cifras"]["carreras"])
        self.assertFalse(portal["noticias"]["activo"])

        configuracion = ConfiguracionPortal.objects.get(pk=1)
        self.assertEqual(configuracion.actualizado_por, self.coordinador)
        cambio = AuditoriaCambio.objects.get(entidad="ConfiguracionPortal")
        self.assertEqual(cambio.accion, "CONFIGURAR_PORTAL_PUBLICO")
        self.assertEqual(cambio.usuario, self.coordinador)
        self.assertIn("facultades", cambio.valores_anteriores_json["cifras"]["opciones"])
        self.assertNotIn("facultades", cambio.valores_nuevos_json["cifras"]["opciones"])

    def test_guardar_sin_cambios_no_ensucia_la_auditoria(self):
        self.client.force_login(self.coordinador)
        self.client.post(self.url, todas_las_opciones())
        self.assertFalse(AuditoriaCambio.objects.filter(entidad="ConfiguracionPortal").exists())

    def test_mapa_encendido_necesita_al_menos_una_vista(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(self.url, todas_las_opciones(
            **{"mapa__proyectos": None, "mapa__socios": None, "cifras__carreras": None}
        ))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "marca al menos una opción")
        # No se guardó nada, pero lo que marcó sigue marcado en pantalla.
        self.assertTrue(configuracion_portal()["cifras"]["carreras"])
        self.assertNotContains(respuesta, 'name="cifras__carreras"\n                                                       checked')
        self.assertFalse(ConfiguracionPortal.objects.filter(opciones_json__has_key="mapa").exists())

    def test_la_pestana_documentos_avisa_si_el_repositorio_esta_oculto(self):
        self.client.force_login(self.coordinador)
        self.client.post(self.url, todas_las_opciones(**{"repositorio__activo": None}))
        respuesta = self.client.get(reverse("archivos:repositorio"))
        self.assertContains(respuesta, "El repositorio está oculto en el portal público")
        self.assertContains(respuesta, "Qué se muestra")


class PortalRespetaConfiguracionTests(DatosPortalMixin, TestCase):
    """El portal público muestra solo lo que eligió el Coordinador."""

    def setUp(self):
        self.crear_datos()

    def configurar(self, **cambios):
        from .portal import _normalizar, leer_formulario

        opciones, errores = leer_formulario(todas_las_opciones(**cambios))
        self.assertEqual(errores, [])
        ConfiguracionPortal.objects.update_or_create(pk=1, defaults={"opciones_json": _normalizar(opciones)})

    def test_por_defecto_muestra_todos_los_bloques(self):
        respuesta = self.inicio()
        self.assertContains(respuesta, 'id="mapaTerritorial"')
        self.assertContains(respuesta, "Cifras Macro del Programa A+S")
        self.assertContains(respuesta, 'id="catalogo"')
        self.assertContains(respuesta, "Noticias y Recursos")
        self.assertContains(respuesta, "ACCEDER AL REPOSITORIO PÚBLICO A+S")

    def test_mapa_apagado_no_se_calcula_ni_se_muestra(self):
        self.configurar(**{"mapa__activo": None})
        respuesta = self.inicio()
        self.assertIsNone(respuesta.context["mapa"])
        self.assertNotContains(respuesta, 'id="mapaTerritorial"')
        self.assertNotContains(respuesta, "Mapa de Impacto Territorial")
        # El catálogo sigue, con sus filtros.
        self.assertContains(respuesta, 'id="catalogo"')
        self.assertContains(respuesta, 'name="comuna"')

    def test_mapa_solo_entrega_los_datos_elegidos(self):
        self.configurar(**{"mapa__socios": None, "mapa__carreras": None, "mapa__anios": None})
        respuesta = self.inicio()
        for punto in respuesta.context["mapa"]["puntos"]:
            self.assertEqual(set(punto), {"comuna", "lat", "lon", "proyectos", "participaciones"})
        # Con una sola vista no se ofrece el selector Proyectos/Socios.
        self.assertNotContains(respuesta, 'data-mapa-modo="socios"')
        self.assertContains(respuesta, 'data-mapa-modo-inicial="proyectos"')

    def test_solo_vista_de_socios(self):
        self.configurar(**{"mapa__proyectos": None})
        respuesta = self.inicio()
        self.assertContains(respuesta, 'data-mapa-modo-inicial="socios"')
        for punto in respuesta.context["mapa"]["puntos"]:
            self.assertNotIn("proyectos", punto)

    def test_cifras_macro_muestra_solo_las_marcadas(self):
        self.configurar(**{"cifras__facultades": None, "cifras__socios": None})
        respuesta = self.inicio()
        self.assertContains(respuesta, "Asignaturas A+S")
        self.assertContains(respuesta, "Carreras Participantes")
        self.assertNotContains(respuesta, "Facultades Involucradas")

    def test_cifras_macro_sin_ninguna_marcada_oculta_la_seccion(self):
        self.configurar(**{f"cifras__{c}": None for c in ("asignaturas", "carreras", "facultades", "socios")})
        self.assertNotContains(self.inicio(), "Cifras Macro del Programa A+S")

    def test_cifras_bajo_el_mapa(self):
        self.configurar(**{"mapa__cifra_estudiantes": None, "mapa__cifra_comunas": None})
        respuesta = self.inicio()
        self.assertContains(respuesta, "Participaciones</div>")
        self.assertNotContains(respuesta, "Estudiantes Participantes")
        self.assertNotContains(respuesta, "Comunas Alcanzadas")

    def test_catalogo_oculta_los_datos_no_elegidos(self):
        self.configurar(**{"catalogo__tipos": None, "catalogo__comunas": None})
        respuesta = self.inicio()
        self.assertContains(respuesta, "Plan de reciclaje")
        self.assertNotContains(respuesta, "bi-tag me-1")
        self.assertNotContains(respuesta, '<i class="bi bi-geo-alt text-danger me-1"')

    def test_catalogo_apagado(self):
        self.configurar(**{"catalogo__activo": None})
        respuesta = self.inicio()
        self.assertEqual(respuesta.context["catalogo"], [])
        self.assertNotContains(respuesta, 'id="catalogo"')
        self.assertNotContains(respuesta, 'href="#catalogo"')

    def test_noticias_apagadas(self):
        Noticia.objects.create(titulo="Noticia visible", url_fuente="https://uautonoma.cl/n/1", estado="PUBLICADA")
        self.assertContains(self.inicio(), "Noticia visible")
        self.configurar(**{"noticias__activo": None})
        self.assertNotContains(self.inicio(), "Noticias y Recursos")

    def test_repositorio_apagado_quita_el_boton_y_la_pagina(self):
        self.configurar(**{"repositorio__activo": None})
        respuesta = self.inicio()
        self.assertNotContains(respuesta, "ACCEDER AL REPOSITORIO PÚBLICO A+S")
        self.assertNotContains(respuesta, reverse("archivos:repositorio_publico"))
        # El aviso para estudiantes no se pierde.
        self.assertContains(respuesta, "¿Eres estudiante?")
        self.assertEqual(self.client.get(reverse("archivos:repositorio_publico")).status_code, 404)


class FiltroTipoSocioTests(DatosPortalMixin, TestCase):
    """CDE-109: filtro público por tipo de socio (clasificación)."""

    def setUp(self):
        self.crear_datos()

    def test_solo_ofrece_tipos_con_participaciones(self):
        opciones = self.inicio().context["opciones"]
        self.assertEqual(
            [c.nombre for c in opciones["clasificaciones"]], ["Emprendedor", "Junta de vecinos"],
        )

    def test_filtra_mapa_cifras_y_catalogo(self):
        respuesta = self.inicio(clasificacion=self.emprendedor.pk)
        self.assertEqual(respuesta.context["filtros"]["clasificacion"], self.emprendedor.pk)
        self.assertTrue(respuesta.context["hay_filtros"])

        puntos = respuesta.context["mapa"]["puntos"]
        self.assertEqual([p["comuna"] for p in puntos], ["Maipú"])
        self.assertEqual(respuesta.context["cifras"]["socios"], 1)
        self.assertEqual(
            [p["servicio"] for p in respuesta.context["catalogo"]], ["Plan de marketing"],
        )
        self.assertContains(respuesta, f'<option value="{self.emprendedor.pk}" selected>')

    def test_se_combina_con_los_demas_filtros(self):
        respuesta = self.inicio(clasificacion=self.junta.pk, comuna=self.maipu.pk)
        self.assertEqual(respuesta.context["mapa"]["puntos"], [])
        self.assertEqual(respuesta.context["catalogo"], [])

    def test_valor_invalido_se_ignora(self):
        respuesta = self.inicio(clasificacion="abc")
        self.assertIsNone(respuesta.context["filtros"]["clasificacion"])
        self.assertEqual(len(respuesta.context["mapa"]["puntos"]), 2)


class PrivacidadYAgregadosTests(DatosPortalMixin, TestCase):
    """CDE-112 / CDE-114: sin datos personales; agregados correctos con históricos."""

    def setUp(self):
        self.crear_datos()

    def test_portal_completo_no_expone_datos_personales(self):
        # Con todo encendido y con cada filtro aplicado.
        variantes = [{}, {"clasificacion": self.junta.pk}, {"comuna": self.providencia.pk}, {"anio": 2024}]
        for parametros in variantes:
            with self.subTest(parametros=parametros):
                html = self.inicio(**parametros).content.decode()
                for dato in (RUT_SOCIO, CORREO_SOCIO, TELEFONO_SOCIO, DIRECCION_SOCIO, NOMBRE_SOCIO, "Rosa Contacto"):
                    self.assertNotIn(dato, html)

    def test_socios_unicos_y_participaciones(self):
        """RF-IND-02: la junta cuenta 1 vez como socio y 2 como participación."""
        respuesta = self.inicio()
        self.assertEqual(respuesta.context["cifras"]["socios"], 2)
        self.assertEqual(respuesta.context["cifras"]["participaciones"], 3)
        providencia = next(p for p in respuesta.context["mapa"]["puntos"] if p["comuna"] == "Providencia")
        self.assertEqual((providencia["socios"], providencia["participaciones"]), (1, 2))

    def test_historicos_sin_periodo_cuentan_por_su_anio(self):
        """CDE-111: la participación histórica (sin período) aparece con su año de inicio."""
        respuesta = self.inicio(anio=2024)
        self.assertEqual([p["comuna"] for p in respuesta.context["mapa"]["puntos"]], ["Providencia"])
        self.assertEqual([p["servicio"] for p in respuesta.context["catalogo"]], ["Huerto comunitario"])
        self.assertEqual([p["anio"] for p in respuesta.context["catalogo"]], [2024])
        self.assertIn(2024, respuesta.context["opciones"]["anios"])


class RendimientoPortalTests(DatosPortalMixin, TestCase):
    """
    CDE-114 / RNF-PER-01: el portal no hace más consultas cuando hay más datos
    y responde rápido con un volumen realista. La prueba de 100 usuarios
    concurrentes (percentil 95) se hace sobre el servidor desplegado.
    """

    def setUp(self):
        self.crear_datos()

    def agregar(self, cantidad):
        comunas = [
            Comuna.objects.create(
                nombre=f"Comuna {n}", region="RM", activo=True,
                lat_centro=-33.4 - n / 1000, lon_centro=-70.6 - n / 1000,
            )
            for n in range(20)
        ]
        for n in range(cantidad):
            socio = self.socio(f"Socio {n}", self.junta if n % 2 else self.emprendedor, comunas[n % 20])
            self.participacion(socio, servicio=f"Servicio {n % 15}", periodo=self.periodo)

    def consultas(self, **parametros):
        self.inicio(**parametros)  # calienta cachés (ContentType, sesión)
        with CaptureQueriesContext(connection) as contexto:
            self.inicio(**parametros)
        return len(contexto.captured_queries)

    def test_las_consultas_no_crecen_con_los_datos(self):
        pocas = self.consultas()
        self.agregar(80)
        self.assertEqual(self.consultas(), pocas)
        self.assertEqual(self.consultas(clasificacion=self.junta.pk), pocas)

    def test_responde_rapido_con_500_participaciones(self):
        self.agregar(500)
        inicio = time.perf_counter()
        respuesta = self.inicio(anio=2026)
        duracion = time.perf_counter() - inicio
        self.assertEqual(respuesta.status_code, 200)
        self.assertGreater(len(respuesta.context["mapa"]["puntos"]), 20)
        self.assertLess(duracion, 3, f"El portal tardó {duracion:.2f} s")
