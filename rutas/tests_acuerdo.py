"""
Ruta del Docente: acuerdo formal descargable para firmar, material de
reflexión de la Coordinación y botón "Marcar como hecha".
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from reportlab import rl_config

from encuestas.definiciones import formalizacion_acuerdos, registro_reflexion
from encuestas.models import RespuestaFormulario, RespuestaPregunta

from .paso_a_paso import MATERIAL_REFLEXION
from .tests_ficha_unica import FichaUnicaBase, publicar


def setUpModule():
    # Sin compresión, el texto del PDF se puede buscar directo.
    global _COMPRESION
    _COMPRESION = rl_config.pageCompression
    rl_config.pageCompression = 0


def tearDownModule():
    rl_config.pageCompression = _COMPRESION


def texto_pdf(contenido):
    return contenido.decode("latin-1")


class AcuerdoFormalTests(FichaUnicaBase):
    def setUp(self):
        super().setUp()
        self.actividad = self.agregar_actividad(11, "Firmar el Acuerdo Formal", etapa="Formalización")
        self.version = publicar(formalizacion_acuerdos.DEFINICION)

    def llenar_acuerdo(self, seccion=None):
        respuesta = RespuestaFormulario.objects.create(
            version=self.version, seccion=seccion or self.seccion, fecha_envio=timezone.now(), es_historica=False,
        )
        valores = {
            "Nombre del Socio Comunitario o representante": "Junta de Vecinos Los Aromos",
            "Compromisos de los estudiantes (enumerar)": "1. Realizar un diagnóstico",
            "Nombre del Director/a de Carrera": "Directora de Prueba",
            "Nombres de los estudiantes firmantes": "Ana Pérez\nLuis Soto",
            "Fecha del acuerdo (DD/MM/AAAA)": "20/11/2026",
        }
        for pregunta in self.version.preguntas.all():
            if pregunta.texto in valores:
                RespuestaPregunta.objects.create(respuesta=respuesta, pregunta=pregunta, valor_texto=valores[pregunta.texto])
        return respuesta

    def test_la_ruta_ofrece_el_acuerdo_llenado_para_firmar_y_el_formato_en_blanco(self):
        respuesta = self.llenar_acuerdo()
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))

        url = reverse("rutas:descargar_acuerdo", args=[self.actividad.id])
        self.assertContains(pagina, f"{url}?respuesta={respuesta.id}")
        self.assertContains(pagina, "Acuerdo 1")
        self.assertContains(pagina, "Descarga el acuerdo en blanco")
        # Ficha única: no se ofrece el Excel para no llenar el acuerdo dos veces.
        self.assertNotContains(pagina, "1rKRBmLowWN_1RZuNRAB9IhvYnx8J9NXz")

    def test_pdf_del_acuerdo_trae_lo_llenado_y_los_firmantes(self):
        respuesta = self.llenar_acuerdo()
        self.client.force_login(self.usuario_docente)

        pdf = self.client.get(reverse("rutas:descargar_acuerdo", args=[self.actividad.id]), {"respuesta": respuesta.id})

        self.assertEqual(pdf["Content-Type"], "application/pdf")
        texto = texto_pdf(pdf.content)
        self.assertIn("FORMALIZACI", texto)
        self.assertIn("Junta de Vecinos Los Aromos", texto)
        self.assertIn("Directora de Prueba", texto)
        self.assertIn("Luis Soto", texto)
        self.assertIn("20/11/2026", texto)
        self.assertIn("Firma Socio Comunitario", texto)

    def test_acuerdo_en_blanco_no_necesita_respuesta(self):
        self.client.force_login(self.usuario_docente)

        pdf = self.client.get(reverse("rutas:descargar_acuerdo", args=[self.actividad.id]))

        self.assertEqual(pdf.status_code, 200)
        texto = texto_pdf(pdf.content)
        self.assertIn("Compromisos de los", texto)
        self.assertIn("Firma Director/a de Carrera", texto)

    def test_no_se_puede_bajar_el_acuerdo_de_otra_seccion(self):
        from academico.models import Seccion

        otra = Seccion.objects.create(
            asignatura=self.seccion.asignatura, periodo=self.seccion.periodo, campus=self.seccion.campus,
            nrc="99999", seccion="9",
        )
        ajena = self.llenar_acuerdo(seccion=otra)
        self.client.force_login(self.usuario_docente)

        pdf = self.client.get(reverse("rutas:descargar_acuerdo", args=[self.actividad.id]), {"respuesta": ajena.id})

        self.assertEqual(pdf.status_code, 404)

    def test_otro_docente_no_puede_bajarlo(self):
        intruso = get_user_model().objects.create_user(username="intruso", password="x")
        self.client.force_login(intruso)

        pdf = self.client.get(reverse("rutas:descargar_acuerdo", args=[self.actividad.id]))

        self.assertEqual(pdf.status_code, 403)


class MaterialYMarcarTests(FichaUnicaBase):
    def test_reflexion_muestra_el_material_de_la_coordinacion(self):
        self.agregar_actividad(12, "Primera actividad de reflexión")
        publicar(registro_reflexion.DEFINICION)
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))

        for material in MATERIAL_REFLEXION:
            self.assertContains(pagina, material["url"])

    def test_marcar_como_hecha_es_un_boton_visible(self):
        self.agregar_actividad(7, "Identificar necesidades")
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))

        self.assertContains(pagina, 'class="btn btn-sm ruta-hecha-btn"')
        self.assertContains(pagina, "presiona")


class QrEnPopupTests(FichaUnicaBase):
    def test_encuestas_de_la_actividad_19_se_muestran_en_un_popup(self):
        from encuestas.definiciones import evaluaciones

        actividad = self.agregar_actividad(19, "Aplicar encuestas de satisfacción", etapa="Cierre y reporte")
        publicar(evaluaciones.ESTUDIANTES)
        publicar(evaluaciones.DOCENTES)
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))

        self.assertContains(pagina, f'data-bs-target="#qr-{actividad.id}"')
        self.assertContains(pagina, f'id="qr-{actividad.id}"')
        self.assertContains(pagina, evaluaciones.ESTUDIANTES["titulo"])
        self.assertContains(pagina, evaluaciones.DOCENTES["titulo"])
        self.assertContains(pagina, f"ruta={self.ruta.id}")

    def test_pagina_de_qr_vuelve_a_la_ruta_si_vino_desde_ella(self):
        self.client.force_login(self.usuario_docente)
        url = reverse("rutas:formularios_qr")

        desde_ruta = self.client.get(url, {"proceso": "EVALUACION_AS", "ruta": self.ruta.id})
        sin_ruta = self.client.get(url, {"proceso": "EVALUACION_AS"})

        self.assertContains(desde_ruta, "Volver a la Ruta")
        self.assertContains(desde_ruta, reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))
        self.assertContains(sin_ruta, "Volver a mis secciones")


class PedirCartaTests(FichaUnicaBase):
    def test_pedir_carta_lleva_al_formulario_de_solicitud(self):
        self.agregar_actividad(10, "Solicitar Carta de Presentación")
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))

        self.assertContains(pagina, reverse("cartas:solicitar_carta_docente", args=[self.seccion.id]))
        self.assertNotContains(pagina, reverse("cartas:listar_cartas_seccion_docente", args=[self.seccion.id]))


class SeccionYEquiposTests(FichaUnicaBase):
    def test_carta_es_una_herramienta_y_no_esta_en_la_informacion(self):
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("core:detalle_seccion", args=[self.seccion.id]))

        self.assertContains(pagina, "Cartas de presentación")
        self.assertContains(pagina, reverse("cartas:listar_cartas_seccion_docente", args=[self.seccion.id]))
        self.assertNotContains(pagina, "+ Solicitar Carta de Presentación")

    def test_equipos_registrados_muestra_resumen(self):
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("proyectos:gestionar_equipos_seccion", args=[self.seccion.id]))

        self.assertEqual(pagina.context["resumen"]["equipos"], 1)
        self.assertEqual(pagina.context["resumen"]["con_socio"], 1)
        self.assertContains(pagina, "Junta de Vecinos")


class VolverSegunOrigenTests(FichaUnicaBase):
    def test_solicitar_carta_vuelve_a_la_ruta_si_vino_desde_ella(self):
        self.agregar_actividad(10, "Solicitar Carta de Presentación")
        self.client.force_login(self.usuario_docente)
        url_ruta = reverse("rutas:detalle_ruta_docente", args=[self.ruta.id])
        url_carta = reverse("cartas:solicitar_carta_docente", args=[self.seccion.id])

        pagina = self.client.get(url_ruta)
        self.assertContains(pagina, f"{url_carta}?volver=")

        desde_ruta = self.client.get(url_carta, {"volver": url_ruta})
        self.assertContains(desde_ruta, "Volver a la Ruta")

        # Recargar la misma página (filtros, formulario con errores) mantiene el origen.
        recarga = self.client.get(url_carta, HTTP_REFERER=f"http://testserver{url_carta}")
        self.assertContains(recarga, "Volver a la Ruta")

        # Entrar desde la sección, sin ?volver, vuelve a la sección.
        url_seccion = reverse("core:detalle_seccion", args=[self.seccion.id])
        desde_seccion = self.client.get(url_carta, HTTP_REFERER=f"http://testserver{url_seccion}")
        self.assertContains(desde_seccion, "Volver a la sección")
        self.assertNotContains(desde_seccion, "Volver a la Ruta")

    def test_volver_no_acepta_otro_sitio(self):
        self.client.force_login(self.usuario_docente)
        url_carta = reverse("cartas:solicitar_carta_docente", args=[self.seccion.id])

        pagina = self.client.get(url_carta, {"volver": "https://malo.example.com/"})

        url_seccion = reverse("core:detalle_seccion", args=[self.seccion.id])
        self.assertContains(pagina, f'<a href="{url_seccion}" class="enlace-volver">')


class InicioAgrupadoTests(FichaUnicaBase):
    def test_rutas_de_un_mismo_ramo_se_agrupan_en_el_inicio(self):
        from academico.models import Seccion, SeccionDocente
        from rutas.models import SeccionRuta

        otra = Seccion.objects.create(
            asignatura=self.seccion.asignatura, periodo=self.seccion.periodo, campus=self.seccion.campus,
            nrc="HU02002", seccion="2", estado="Activo",
        )
        SeccionDocente.objects.create(seccion=otra, docente=self.docente)
        SeccionRuta.objects.create(seccion=otra, ruta_version=self.ruta.ruta_version, estado="EN_PROGRESO", porcentaje_final=0)
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("core:inicio_docente"))

        grupos = pagina.context["grupos_rutas"]
        self.assertEqual(len(grupos), 1)
        self.assertEqual(len(grupos[0]["rutas"]), 2)
        self.assertContains(pagina, "2 secciones")
        self.assertContains(pagina, "NRC HU02002")


class AvisosDocenteTests(FichaUnicaBase):
    def test_inicio_avisa_carta_observada_y_aprobada(self):
        from cartas.models import SolicitudCarta

        datos = dict(
            seccion=self.seccion, campus=self.seccion.campus, sede=self.seccion.campus.sede,
            docente_derivador=self.docente, solicitante_tipo="DOCENTE", solicitante_nombre="Docente",
            solicitante_correo="docente@uautonoma.cl", persona_receptora="Persona", cargo_receptor="Cargo",
            fecha_solicitud=timezone.now(),
        )
        SolicitudCarta.objects.create(
            **datos, institucion_receptora="Junta Observada", estado="OBSERVADA", motivo_observacion="Falta el cargo",
        )
        SolicitudCarta.objects.create(
            **datos, institucion_receptora="Junta Aprobada", estado="APROBADA", fecha_aprobacion=timezone.now(),
        )
        self.client.force_login(self.usuario_docente)

        pagina = self.client.get(reverse("core:inicio_docente"))

        self.assertContains(pagina, "Carta para Junta Observada observada")
        self.assertContains(pagina, "Falta el cargo")
        self.assertContains(pagina, "Carta para Junta Aprobada aprobada")
        self.assertContains(pagina, "Revisa tu bandeja", count=0)


class ResumenPrecargadoTests(FichaUnicaBase):
    def test_resumen_final_trae_lo_del_proyecto_socios_secciones_y_encuestas(self):
        from encuestas import precarga
        from encuestas import services as encuestas_services
        from encuestas.definiciones import formulario_proyecto_as, resumen_implementacion
        from socios.models import ClasificacionSocio

        clasificacion = ClasificacionSocio.objects.create(nombre="Junta de Vecinos", activo=True)
        self.socio.clasificacion = clasificacion
        self.socio.save()
        encuestas = self.agregar_actividad(19, "Aplicar encuestas de satisfacción")
        encuestas.completada_por_docente = self.docente
        encuestas.save()

        proyecto = publicar(formulario_proyecto_as.DEFINICION)
        respuesta = RespuestaFormulario.objects.create(
            version=proyecto, seccion=self.seccion, fecha_envio=timezone.now(), es_historica=False,
        )
        for pregunta in proyecto.preguntas.filter(texto__in=["Objetivo del Servicio", "Servicio que harán los estudiantes"]):
            RespuestaPregunta.objects.create(respuesta=respuesta, pregunta=pregunta, valor_texto=f"texto de {pregunta.texto}")

        version = publicar(resumen_implementacion.DEFINICION)
        _, preguntas = encuestas_services.cargar_estructura(version)
        inicial, _ = precarga.precargar(version, preguntas, self.seccion, self.usuario_docente)
        por_texto = {p.texto: inicial.get(encuestas_services.nombre_campo(p)) for p in preguntas}

        consistio = next(v for t, v in por_texto.items() if t.startswith("¿En que consistió"))
        self.assertIn("Objetivo: texto de Objetivo del Servicio", consistio)
        self.assertIn("Servicio: texto de Servicio que harán los estudiantes", consistio)
        self.assertEqual(por_texto["¿Cuantas secciones de una misma asignatura tiene a su cargo?"], 1)
        self.assertTrue(por_texto["¿Qué secciones desea reportar?"])
        tipos = next(v for t, v in por_texto.items() if t.startswith("Tipo de socios comunitarios"))
        self.assertEqual(len(tipos), 1)
        aplico = next(v for t, v in por_texto.items() if t.startswith("¿Aplicó las 3 encuestas"))
        self.assertTrue(aplico)
