"""
Socios que el Docente elige para su sección (RF-SC-03) y que ven los
estudiantes al registrar su equipo (HU-03, RF-EQP-04, RF-SC-04).
"""
from django.test import TestCase
from django.urls import reverse

from auditoria.models import AuditoriaCambio
from core import indicadores
from proyectos import catalogo
from proyectos import tests as tests_registro
from socios import services
from socios.models import ParticipacionSocio
from socios.tests import crear_socio


class SociosDeLaSeccionTests(TestCase):
    # Mismos datos que las pruebas del registro de equipos (CDE-48).
    setUp = tests_registro.RegistroEquiposCDE48Tests.setUp
    datos_registro_validos = tests_registro.RegistroEquiposCDE48Tests.datos_registro_validos

    def elegir(self, socio, seccion=None, accion="elegir"):
        self.client.force_login(self.usuario_docente)
        return self.client.post(
            reverse("socios:elegir_socio_seccion", args=[(seccion or self.seccion).pk]),
            {"socio": socio.pk, "accion": accion},
        )

    def test_docente_elige_y_quita_socio_con_auditoria(self):
        socio = crear_socio("Fundación Elegida")

        self.elegir(socio)
        self.elegir(socio)  # repetir no duplica
        self.assertEqual(list(services.socios_elegidos_seccion(self.seccion)), [socio])
        eleccion = ParticipacionSocio.objects.get(socio=socio)
        self.assertIsNone(eleccion.equipo)
        self.assertEqual(eleccion.seccion, self.seccion)
        self.assertEqual(eleccion.asignatura, self.asignatura)

        self.elegir(socio, accion="quitar")
        self.assertFalse(services.socios_elegidos_seccion(self.seccion).exists())
        eleccion.refresh_from_db()
        self.assertIsNotNone(eleccion.fecha_fin)  # se cierra, no se borra
        self.assertEqual(
            set(AuditoriaCambio.objects.filter(entidad="Seccion").values_list("accion", flat=True)),
            {"ELEGIR_SOCIO_SECCION", "QUITAR_SOCIO_SECCION"},
        )

    def test_docente_no_puede_elegir_para_seccion_ajena(self):
        socio = crear_socio("Fundación Ajena")
        respuesta = self.elegir(socio, seccion=self.seccion_otra)
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(ParticipacionSocio.objects.exists())

    def test_estudiante_solo_ve_los_socios_de_su_seccion(self):
        elegido = crear_socio("Fundación Elegida")
        crear_socio("Otra Fundación")
        self.elegir(elegido)

        self.client.force_login(self.usuario_estudiante)
        respuesta = self.client.get(self.url_registro)
        self.assertEqual(list(respuesta.context["socios_disponibles"]), [elegido])
        self.assertTrue(respuesta.context["socios_de_la_seccion"])

    def test_sin_socios_elegidos_ve_el_catalogo_completo(self):
        crear_socio("Fundación Uno")
        crear_socio("Fundación Dos")
        self.client.force_login(self.usuario_estudiante)
        respuesta = self.client.get(self.url_registro)
        self.assertEqual(len(respuesta.context["socios_disponibles"]), 2)
        self.assertFalse(respuesta.context["socios_de_la_seccion"])

    def test_no_acepta_un_socio_fuera_de_los_elegidos(self):
        elegido = crear_socio("Fundación Elegida")
        otro = crear_socio("Otra Fundación")
        self.elegir(elegido)

        self.client.force_login(self.usuario_estudiante)
        datos = self.datos_registro_validos()
        datos.update(tipo_socio="existente", socio_comunitario=str(otro.pk))
        self.client.post(self.url_registro, datos)
        self.assertFalse(self.seccion.equipos.exists())

        datos = self.datos_registro_validos()
        datos.update(tipo_socio="existente", socio_comunitario=str(elegido.pk))
        self.client.post(self.url_registro, datos)
        equipo = self.seccion.equipos.get()
        self.assertEqual(equipo.socio_vigente, elegido)

    def test_la_eleccion_no_cuenta_como_participacion(self):
        socio = crear_socio("Fundación Elegida")
        self.elegir(socio)

        filtros = {nombre: None for nombre in indicadores.FILTROS}
        self.assertFalse(indicadores.participaciones_filtradas(filtros).exists())
        en_curso, totales = catalogo.proyectos(catalogo.leer_filtros({}))
        self.assertEqual(sum(totales.values()), 0)
        self.assertFalse(socio.participaciones.trabajadas().exists())

    def test_catalogo_docente_marca_los_elegidos(self):
        elegido = crear_socio("Fundación Elegida")
        crear_socio("Otra Fundación")
        self.elegir(elegido)

        respuesta = self.client.get(reverse("socios:catalogo_docente"), {"seccion": self.seccion.pk})
        marcados = {s.nombre_organizacion for s in respuesta.context["socios"] if s.elegido}
        self.assertEqual(marcados, {"Fundación Elegida"})
        self.assertEqual(respuesta.context["total_elegidos"], 1)

        ajena = self.client.get(reverse("socios:catalogo_docente"), {"seccion": self.seccion_otra.pk})
        self.assertEqual(ajena.status_code, 403)

    def test_carta_sugiere_los_socios_de_la_seccion_con_su_contacto(self):
        from cartas.forms import sugerencias_receptor
        from socios.models import ContactoSocio

        elegido = crear_socio("Fundación Elegida")
        crear_socio("Otra Fundación")
        ContactoSocio.objects.create(
            socio=elegido, nombre="María Pérez", cargo="Directora", es_principal=True, activo=True,
        )
        self.elegir(elegido)
        self.assertEqual(
            sugerencias_receptor(self.seccion),
            [{"institucion": "Fundación Elegida", "persona": "María Pérez", "cargo": "Directora"}],
        )
