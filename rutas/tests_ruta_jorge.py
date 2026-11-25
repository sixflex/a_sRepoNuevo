"""
Detalles de la Ruta de Jorge (PDF interactivo): contacto con Coordinación,
carta pedida por un estudiante con QR y cómo se hace cada dinámica.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from cartas.models import EnlaceSolicitudCarta
from encuestas.definiciones import formalizacion_acuerdos, registro_reflexion

from .tests_ficha_unica import FichaUnicaBase, publicar


class RutaDeJorgeTests(FichaUnicaBase):
    def ver_ruta(self):
        self.client.force_login(self.usuario_docente)
        return self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))

    def test_reunion_inicial_escribe_a_coordinacion(self):
        coordinador = get_user_model().objects.create_user(
            username="jorge", password="x", correo_institucional="coordinacion@uautonoma.cl",
        )
        coordinador.groups.add(Group.objects.get_or_create(name="Coordinador")[0])
        self.agregar_actividad(2, "Coordinar reunión inicial con Coordinación A+S")

        pagina = self.ver_ruta()

        self.assertContains(pagina, "mailto:coordinacion@uautonoma.cl?subject=")
        self.assertContains(pagina, "Escribir a Coordinación")

    def test_carta_tambien_con_qr_para_estudiantes(self):
        actividad = self.agregar_actividad(10, "Solicitar Carta de Presentación")

        pagina = self.ver_ruta()

        enlace = EnlaceSolicitudCarta.objects.get(seccion=self.seccion)
        self.assertContains(pagina, reverse("cartas:solicitar_carta_estudiante", args=[enlace.token]))
        self.assertContains(pagina, f'data-bs-target="#qr-{actividad.id}"')
        self.assertContains(pagina, reverse("cartas:solicitar_carta_docente", args=[self.seccion.id]))

        self.ver_ruta()
        self.assertEqual(EnlaceSolicitudCarta.objects.filter(seccion=self.seccion).count(), 1)

    def test_dinamicas_con_duracion_y_ficha(self):
        self.agregar_actividad(15, "Realizar segunda actividad de reflexión")
        publicar(registro_reflexion.DEFINICION)

        pagina = self.ver_ruta()

        self.assertContains(pagina, "Mesa redonda")
        self.assertContains(pagina, "pide los dados a Coordinación")

    def test_acuerdo_pide_calendarizacion(self):
        textos = [p["texto"] for s in formalizacion_acuerdos.DEFINICION["secciones"] for p in s["preguntas"]]
        self.assertIn("Calendarización de las actividades y fechas importantes", textos)

    def test_docente_que_abre_el_qr_de_la_carta_puede_cambiar_de_cuenta(self):
        self.agregar_actividad(10, "Solicitar Carta de Presentación")
        self.ver_ruta()
        enlace = EnlaceSolicitudCarta.objects.get(seccion=self.seccion)

        pagina = self.client.get(reverse("cartas:solicitar_carta_estudiante", args=[enlace.token]))

        self.assertEqual(pagina.status_code, 403)
        self.assertContains(pagina, "Cerrar sesión e ingresar como estudiante", status_code=403)
        self.assertNotContains(pagina, "Mis secciones", status_code=403)

    def test_documentacion_final_muestra_la_carpeta_y_se_descarga(self):
        self.agregar_actividad(22, "Enviar documentación final", etapa="Cierre y reporte")

        pagina = self.ver_ruta()

        self.assertContains(pagina, "Acuerdos firmados (actividad 11)")
        self.assertContains(pagina, "Reflexiones registradas (12, 15 y 17)")
        url = reverse("rutas:descargar_mi_carpeta", args=[self.ruta.id])
        self.assertContains(pagina, url)
        zip_ = self.client.get(url)
        self.assertEqual(zip_.status_code, 200)
        self.assertEqual(zip_["Content-Type"], "application/zip")

    def test_otro_docente_no_descarga_la_carpeta(self):
        otro = get_user_model().objects.create_user(username="otro", password="x")
        otro.groups.add(Group.objects.get_or_create(name="Docente")[0])
        self.client.force_login(otro)
        respuesta = self.client.get(reverse("rutas:descargar_mi_carpeta", args=[self.ruta.id]))
        self.assertEqual(respuesta.status_code, 403)


class FichaUnicaCierreTests(FichaUnicaBase):
    """Lo que los grupos llenan en el semestre llega al Resumen y a la ficha."""

    def setUp(self):
        super().setUp()
        from socios.models import ParticipacionSocio

        ParticipacionSocio.objects.filter(seccion=self.seccion).update(
            beneficiarios_estimados=40, servicio_realizado="Talleres de huerto",
            evaluacion=5, comentario="Muy comprometidos",
        )

    def test_resumen_trae_los_beneficiarios_de_los_grupos(self):
        from encuestas.precarga import datos_seccion

        datos = datos_seccion(self.seccion)
        self.assertEqual(datos["beneficiarios"], 40)
        self.assertNotIn("documentacion", datos)

    def test_resumen_marca_la_documentacion_con_la_actividad_22_hecha(self):
        from encuestas.precarga import datos_seccion

        actividad = self.agregar_actividad(22, "Enviar documentación final")
        actividad.completada_por_docente = self.docente
        actividad.save()
        self.assertEqual(datos_seccion(self.seccion)["documentacion"], "Si")

    def test_ficha_del_coordinador_muestra_el_trabajo_de_cada_grupo(self):
        self.ruta.estado = "COMPLETADA"
        self.ruta.save(update_fields=["estado"])
        self.client.force_login(self.usuario_coordinador)

        pagina = self.client.get(reverse("rutas:ver_ficha_coordinacion", args=[self.ruta.id]))

        self.assertContains(pagina, "Trabajo con el socio")
        self.assertContains(pagina, "Talleres de huerto")
        self.assertContains(pagina, "socio@example.com")
        pdf = self.client.get(reverse("rutas:descargar_expediente", args=[self.ruta.id]))
        self.assertEqual(pdf.status_code, 200)


class CartaEstudianteQrTests(FichaUnicaBase):
    def test_el_estudiante_que_escanea_el_qr_ve_el_formulario(self):
        estudiante = get_user_model().objects.create_user(username="est", password="x")
        estudiante.groups.add(Group.objects.get_or_create(name="Estudiante")[0])
        self.agregar_actividad(10, "Solicitar Carta de Presentación")
        self.client.force_login(self.usuario_docente)
        self.client.get(reverse("rutas:detalle_ruta_docente", args=[self.ruta.id]))
        enlace = EnlaceSolicitudCarta.objects.get(seccion=self.seccion)

        self.client.force_login(estudiante)
        pagina = self.client.get(reverse("cartas:solicitar_carta_estudiante", args=[enlace.token]))

        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, "<form")
