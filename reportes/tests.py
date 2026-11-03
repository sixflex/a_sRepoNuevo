from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from socios.centros_sercotec import normalizar_centro
from socios.models import ContactoSocio, ParticipacionSocio, SocioComunitario


class NormalizarCentroTests(SimpleTestCase):
    def test_textos_libres_llegan_al_nombre_oficial(self):
        oficial = "Centro de Negocios Sercotec Santiago"
        for texto in ("Santiago", "STGO", "CDN Santiago", "centro de negocios sercotec santiago"):
            self.assertEqual(normalizar_centro(texto), oficial)
        self.assertEqual(normalizar_centro("CDN Las Condes"), "Centro de Negocios Sercotec Las Condes")
        self.assertEqual(normalizar_centro("San Jose de Maipo"), "Centro de Negocios Sercotec San José de Maipo")

    def test_lo_que_no_se_reconoce_queda_en_none(self):
        self.assertIsNone(normalizar_centro("No estoy asociado"))
        self.assertIsNone(normalizar_centro(""))
        self.assertIsNone(normalizar_centro(None))


def socio(nombre, **datos):
    return SocioComunitario.objects.create(
        nombre_organizacion=nombre, estado_revision="APROBADO", es_provisional=False,
        activo=True, fecha_creacion=timezone.now(), **datos,
    )


def participacion(socio_, anio):
    return ParticipacionSocio.objects.create(
        socio=socio_, origen="HISTORICO", fecha_inicio=f"{anio}-04-01", fecha_fin=f"{anio}-07-01",
    )


def leer(response):
    return load_workbook(BytesIO(response.content))


class ReportesTests(TestCase):
    def setUp(self):
        self.coordinador = get_user_model().objects.create_user(username="coord", password="x")
        self.coordinador.groups.add(Group.objects.create(name="Coordinador"))
        self.client.force_login(self.coordinador)

        self.almacen = socio("Almacén Rosa", rut="11111111-1", centro_servicio="STGO")
        ContactoSocio.objects.create(
            socio=self.almacen, nombre="Rosa", correo="rosa@a.cl", telefono="0912345678",
            es_principal=True, activo=True,
        )
        self.taller = socio("Taller Juan", centro_servicio="Centro de Negocios Sercotec Santiago")
        self.feria = socio("Feria Libre")
        participacion(self.almacen, 2025)
        participacion(self.almacen, 2025)
        participacion(self.taller, 2025)
        participacion(self.feria, 2024)
        # Postuló pero ningún docente lo eligió: no debe aparecer.
        socio("Solo postulante", centro_servicio="Santiago")

    def test_pagina_de_reportes_solo_para_coordinacion(self):
        self.assertEqual(self.client.get(reverse("reportes:inicio")).status_code, 200)

        docente = get_user_model().objects.create_user(username="doc", password="x")
        docente.groups.add(Group.objects.create(name="Docente"))
        self.client.force_login(docente)
        self.assertEqual(self.client.get(reverse("reportes:centros_sercotec")).status_code, 403)

    def test_emprendedores_por_centro_y_anio(self):
        libro = leer(self.client.get(reverse("reportes:centros_sercotec")))

        filas = [fila for fila in libro["Resumen por centro"].iter_rows(values_only=True)]
        encabezado = filas.index(("Centro SERCOTEC", "Año", "Emprendedores", "Participaciones"))
        resumen = filas[encabezado + 1:]
        # "STGO" y el nombre oficial quedan juntos; quien no trabajó no cuenta.
        self.assertIn(("Centro de Negocios Sercotec Santiago", 2025, 2, 3), resumen)
        self.assertIn(("Sin centro SERCOTEC", 2024, 1, 1), resumen)

        detalle = [fila for fila in libro["Emprendedores"].iter_rows(values_only=True)]
        rosa = next(fila for fila in detalle if fila[2] == "Almacén Rosa")
        self.assertEqual(rosa[3], "11111111-1")
        self.assertEqual(rosa[7], "0912345678")  # teléfono como texto, con su 0
        self.assertNotIn("Solo postulante", [fila[2] for fila in detalle])

    def test_participaciones_respeta_filtros_y_los_anota(self):
        response = self.client.get(reverse("reportes:participaciones"), {"anio": 2024})
        hoja = leer(response)["Participaciones"]
        valores = [fila for fila in hoja.iter_rows(values_only=True)]

        socios = [fila[11] for fila in valores if fila and len(fila) > 11 and fila[0] == 2024]
        self.assertEqual(socios, ["Feria Libre"])
        self.assertTrue(any(fila[0] == "Filtros aplicados" and "2024" in str(fila[1]) for fila in valores))

    def test_sin_filtros_parte_con_todos_los_anios(self):
        hoja = leer(self.client.get(reverse("reportes:participaciones")))["Participaciones"]
        anios = {fila[0] for fila in hoja.iter_rows(values_only=True) if fila and fila[0] in (2024, 2025)}
        self.assertEqual(anios, {2024, 2025})
