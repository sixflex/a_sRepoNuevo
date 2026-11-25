"""
Equipo ya registrado: cualquier integrante cuenta el trabajo con el socio
y el docente agrega o quita integrantes (RF-EQP-07, RF-SC-04..06).
"""
import uuid

from django.test import TestCase
from django.urls import reverse

from auditoria.models import AuditoriaCambio
from proyectos.models import Equipo, IntegranteEquipo
from proyectos.tests import RegistroEquiposCDE48Tests


class EquipoRegistradoTests(TestCase):
    setUp = RegistroEquiposCDE48Tests.setUp
    datos_registro_validos = RegistroEquiposCDE48Tests.datos_registro_validos

    def registrar(self):
        self.client.force_login(self.usuario_estudiante)
        datos = self.datos_registro_validos()
        datos.update({
            "cantidad_integrantes": "2", "rut_2": "11.111.111-1", "nombres_2": "ana maría",
            "apellidos_2": "DE LA FUENTE", "correo_2": "ana@cloud.uautonoma.cl",
        })
        respuesta = self.client.post(self.url_registro, datos)
        self.assertEqual(respuesta.status_code, 302)
        return Equipo.objects.get(seccion=self.seccion)

    def segundo_integrante(self):
        return self.User.objects.create_user(
            username="ana", password="x", email="ana@cloud.uautonoma.cl",
            correo_institucional="ana@cloud.uautonoma.cl", activo=True,
        )

    def test_registro_guarda_socio_normalizado_y_nombres(self):
        equipo = self.registrar()
        socio = equipo.socio_vigente
        self.assertEqual(socio.comuna.nombre, "Providencia")
        ana = equipo.integrantes.get(correo_institucional="ana@cloud.uautonoma.cl")
        self.assertEqual((ana.nombres, ana.apellidos), ("Ana María", "De la Fuente"))

    def test_registro_rechaza_comuna_desconocida(self):
        self.client.force_login(self.usuario_estudiante)
        datos = self.datos_registro_validos()
        datos["socio_comuna"] = "Ciudad Gótica"
        respuesta = self.client.post(self.url_registro, datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Equipo.objects.exists())

    def test_otro_integrante_guarda_el_trabajo_aunque_el_enlace_cerro(self):
        equipo = self.registrar()
        self.enlace.activo = False
        self.enlace.save()
        usuario = self.segundo_integrante()
        usuario.groups.add(self.grupo_estudiante)
        self.client.force_login(usuario)

        pagina = self.client.get(self.url_registro)
        self.assertContains(pagina, "Trabajo con el socio")

        respuesta = self.client.post(self.url_registro, {
            "accion": "trabajo_socio", "beneficiarios_estimados": "40",
            "servicio_realizado": "Talleres de alfabetización digital", "evaluacion": "5",
            "comentario": "Muy buena disposición",
        })
        self.assertEqual(respuesta.status_code, 302)
        participacion = equipo.participaciones_socios.get(fecha_fin__isnull=True)
        self.assertEqual(participacion.beneficiarios_estimados, 40)
        self.assertEqual(participacion.evaluacion, 5)

    def test_reenvio_del_registro_no_guarda_trabajo(self):
        equipo = self.registrar()
        self.client.post(self.url_registro, self.datos_registro_validos(clave=uuid.uuid4()))
        self.assertEqual(Equipo.objects.filter(seccion=self.seccion).count(), 1)
        participacion = equipo.participaciones_socios.get(fecha_fin__isnull=True)
        self.assertIsNone(participacion.evaluacion)

    def test_docente_agrega_y_quita_integrante_con_auditoria(self):
        equipo = self.registrar()
        self.client.force_login(self.usuario_docente)
        url = reverse("proyectos:gestionar_equipo", kwargs={"equipo_id": equipo.id})

        self.client.post(url, {
            "accion": "agregar_integrante", "rut": "9.999.999-3", "nombres": "PEDRO",
            "apellidos": "soto", "correo": "Pedro@cloud.uautonoma.cl",
        })
        pedro = equipo.integrantes.get(correo_institucional="pedro@cloud.uautonoma.cl")
        self.assertEqual(pedro.nombres, "Pedro")


        self.client.post(url, {
            "accion": "agregar_integrante", "rut": "5.555.555-5", "nombres": "Otro",
            "apellidos": "Más", "correo": "pedro@cloud.uautonoma.cl",
        })
        self.assertEqual(equipo.integrantes.count(), 3)

        self.client.post(url, {"accion": "quitar_integrante", "integrante_id": pedro.id})
        self.assertFalse(IntegranteEquipo.objects.filter(pk=pedro.pk).exists())
        acciones = set(AuditoriaCambio.objects.filter(entidad="Equipo", entidad_id=equipo.pk)
                       .values_list("accion", flat=True))
        self.assertTrue({"AGREGAR_INTEGRANTE", "QUITAR_INTEGRANTE"} <= acciones)

    def test_no_se_quita_el_ultimo_integrante(self):
        equipo = self.registrar()
        equipo.integrantes.exclude(correo_institucional=self.usuario_estudiante.correo_institucional).delete()
        self.client.force_login(self.usuario_docente)
        url = reverse("proyectos:gestionar_equipo", kwargs={"equipo_id": equipo.id})
        unico = equipo.integrantes.get()
        self.client.post(url, {"accion": "quitar_integrante", "integrante_id": unico.id})
        self.assertTrue(IntegranteEquipo.objects.filter(pk=unico.pk).exists())
