from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import AuditoriaCambio
from comunicaciones.models import EnvioCorreo
from socios.services import historial_estados_socio
from encuestas.models import FormularioPlantilla, FormularioVersion, RespuestaFormulario
from socios.models import Convocatoria, PostulacionSocio, SocioComunitario
from socios import views as socios_views
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
        # Propuesto por un equipo y aprobado solo para el historial de ese
        # equipo: sigue provisional. Los Recibidos se revisan en Postulaciones.
        cls.norte = crear_socio(
            "Junta Norte", rut="65.987.654-3",
            clasificacion=cls.clasif_junta, comuna=cls.comuna_b,
            estado_revision="APROBADO", es_provisional=True,
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
        cls.asignado = crear_socio(
            "Club Asignado", rut="74.555.666-7", estado_revision="ASIGNADO",
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
        self.assertEqual(len(nombres(resp)), 7)

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
            self.url, {"estado": "APROBADO", "provisional": "1", "comuna": self.comuna_b.id}
        )
        self.assertEqual(nombres(resp), {"Junta Norte"})

    def test_filtros_combinados_sin_coincidencia(self):
        resp = self.client.get(self.url, {"estado": "DISPONIBLE", "provisional": "1"})
        self.assertEqual(nombres(resp), set())

    def test_vista_disponibles(self):
        resp = self.client.get(self.url, {"vista": "disponibles"})
        self.assertEqual(nombres(resp), {"Fundación Esperanza", "Centro Disponible", "Club Asignado"})

    def test_vista_solo_historial(self):
        resp = self.client.get(self.url, {"vista": "historial"})
        self.assertEqual(nombres(resp), {"Taller Terminado", "Grupo Inactivo"})


class CatalogoDocenteTests(DatosBase):
    """CDE-60: el catálogo solo muestra socios aprobados, disponibles o asignados."""

    def setUp(self):
        self.client.force_login(self.docente)
        self.url = reverse("socios:catalogo_docente")

    def test_muestra_aprobados_disponibles_y_asignados(self):
        # RN-09: un socio asignado puede trabajar con varios equipos.
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(nombres(resp), {"Fundación Esperanza", "Centro Disponible", "Club Asignado"})

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
        # Socio propuesto por un equipo que aún no se revisa.
        self.norte = crear_socio(
            "Junta Sur Propuesta", rut="66.111.222-4", estado_revision="RECIBIDO", es_provisional=True,
        )

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

    def test_ciclo_del_socio_aprobado_queda_auditado(self):
        # RF-SC-02: Disponible -> Asignado -> Trabajo terminado, y puede volver.
        for estado in ("ASIGNADO", "TRABAJO_TERMINADO", "DISPONIBLE"):
            self.client.post(self.url_cambio(self.disponible), {"estado_revision": estado})

        self.disponible.refresh_from_db()
        self.assertEqual(self.disponible.estado_revision, "DISPONIBLE")
        cambios = [
            (c.valores_anteriores_json["estado_revision"], c.valores_nuevos_json["estado_revision"])
            for c in historial_estados_socio(self.disponible).order_by("id")
        ]
        self.assertEqual(cambios, [
            ("DISPONIBLE", "ASIGNADO"),
            ("ASIGNADO", "TRABAJO_TERMINADO"),
            ("TRABAJO_TERMINADO", "DISPONIBLE"),
        ])

    def test_socio_recibido_no_salta_la_aprobacion(self):
        resp = self.client.post(
            self.url_cambio(self.norte), {"estado_revision": "ASIGNADO"}, follow=True,
        )

        self.norte.refresh_from_db()
        self.assertEqual(self.norte.estado_revision, "RECIBIDO")
        self.assertContains(resp, "no puede pasar a «Asignado»")
        self.assertFalse(historial_estados_socio(self.norte).exists())

    def test_modal_ofrece_solo_los_estados_permitidos(self):
        resp = self.client.get(reverse("socios:lista_coordinador"))
        socios = {socio.nombre_organizacion: socio for socio in resp.context["socios"]}

        self.assertNotIn("Junta Sur Propuesta", socios)
        self.assertEqual(
            [valor for valor, _ in socios["Club Rechazado"].estados_siguientes],
            ["APROBADO", "RECHAZADO"],
        )
        self.assertIn("ASIGNADO", dict(socios["Centro Disponible"].estados_siguientes))

    def test_estado_antiguo_fuera_de_la_lista_puede_cambiar(self):
        socio = crear_socio("Junta Antigua", rut="75.666.777-8", estado_revision="EN_REVISION")

        self.client.post(self.url_cambio(socio), {"estado_revision": "APROBADO"})

        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "APROBADO")

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

    def test_postulacion_publica_sin_barra_del_portal(self):
        url = reverse("socios:postular_convocatoria", args=[self.convocatoria_activa.id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "navbar-sistema")

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

class SincronizacionEstadosTests(TestCase):
    """RF-SC-02: postulación y socio cambian por un solo servicio, con historial."""

    def setUp(self):
        self.coordinador = crear_usuario("Coordinador")
        self.client.force_login(self.coordinador)

        plantilla = FormularioPlantilla.objects.create(
            codigo="POST-SYNC", titulo="Postulación", proceso="POSTULACION", activo=True,
        )
        self.version = FormularioVersion.objects.create(
            plantilla=plantilla, numero_version=1, estado="PUBLICADO", fecha_creacion=timezone.now(),
        )
        self.convocatoria = Convocatoria.objects.create(
            formulario_version=self.version, nombre="Convocatoria 2026",
            fecha_inicio=timezone.now(), estado="PUBLICADA",
        )

    def crear_postulacion(self, socio, estado="RECIBIDA"):
        respuesta = RespuestaFormulario.objects.create(
            version=self.version, fecha_envio=timezone.now(), origen="PUBLICO",
            es_historica=False, respondente_correo="contacto@socio.cl",
            respondente_rut=socio.rut, estado_registro="COMPLETO",
        )
        return PostulacionSocio.objects.create(
            convocatoria=self.convocatoria, respuesta_formulario=respuesta, socio=socio,
            estado=estado, fecha_recepcion=timezone.now(),
        )

    def revisar(self, postulacion, decision, motivo=""):
        return self.client.post(
            reverse("socios:revisar_postulacion", args=[postulacion.id]),
            {"estado": decision, "motivo_rechazo": motivo},
            follow=True,
        )

    def cambiar(self, socio, estado, **extra):
        datos = {"estado_revision": estado}
        datos.update(extra)
        return self.client.post(reverse("socios:cambiar_estado", args=[socio.id]), datos, follow=True)

    def test_aprobar_postulacion_aprueba_al_socio_con_historial(self):
        socio = crear_socio("Junta Sur", rut="11111111-1", estado_revision="RECIBIDO", es_provisional=True)
        postulacion = self.crear_postulacion(socio)

        self.revisar(postulacion, "APROBADA")

        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "APROBADO")
        self.assertFalse(socio.es_provisional)
        cambio = historial_estados_socio(socio).get()
        self.assertEqual(cambio.valores_anteriores_json["estado_revision"], "RECIBIDO")
        self.assertEqual(cambio.valores_nuevos_json["estado_revision"], "APROBADO")
        self.assertEqual(cambio.usuario, self.coordinador)
        self.assertIsNotNone(cambio.fecha)
        revision = AuditoriaCambio.objects.get(entidad="PostulacionSocio", entidad_id=str(postulacion.id))
        self.assertEqual(revision.valores_nuevos_json["estado"], "APROBADA")
        self.assertIsNotNone(cambio.fecha)

    def test_rechazar_postulacion_rechaza_al_socio_y_notifica(self):
        socio = crear_socio("Junta Sur", rut="11111111-1", estado_revision="RECIBIDO", es_provisional=True)
        postulacion = self.crear_postulacion(socio)

        self.revisar(postulacion, "RECHAZADA", "Fuera del territorio de la sede.")

        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "RECHAZADO")
        cambio = historial_estados_socio(socio).get()
        self.assertEqual(cambio.valores_nuevos_json["estado_revision"], "RECHAZADO")
        self.assertEqual(cambio.valores_nuevos_json["motivo_rechazo"], "Fuera del territorio de la sede.")
        postulacion.refresh_from_db()
        self.assertEqual(postulacion.motivo_rechazo, "Fuera del territorio de la sede.")
        correo = EnvioCorreo.objects.get(postulacion=postulacion)
        self.assertIn("próxima convocatoria", correo.cuerpo)

    def test_postulacion_revisada_no_se_puede_revisar_otra_vez(self):
        socio = crear_socio("Junta Sur", rut="11111111-1", estado_revision="APROBADO")
        postulacion = self.crear_postulacion(socio, estado="APROBADA")

        response = self.revisar(postulacion, "RECHAZADA", "Cambio de opinión")

        postulacion.refresh_from_db()
        self.assertEqual(postulacion.estado, "APROBADA")
        self.assertContains(response, "ya fue revisada")

    def test_socio_disponible_que_vuelve_a_postular_conserva_su_estado(self):
        socio = crear_socio("Centro Activo", rut="11111111-1", estado_revision="DISPONIBLE")
        postulacion = self.crear_postulacion(socio)

        self.revisar(postulacion, "RECHAZADA", "Ya participa en otra convocatoria.")

        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "DISPONIBLE")

    def test_catalogo_no_se_salta_una_postulacion_pendiente(self):
        socio = crear_socio("Junta Sur", rut="11111111-1", estado_revision="RECIBIDO", es_provisional=True)
        postulacion = self.crear_postulacion(socio)

        response = self.cambiar(socio, "DISPONIBLE")

        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "RECIBIDO")
        self.assertContains(response, f"postulación pendiente (folio #{postulacion.id})")
        self.assertFalse(historial_estados_socio(socio).exists())

    def test_catalogo_no_muestra_postulantes_sin_aceptar(self):
        pendiente = crear_socio("Junta Pendiente", rut="11111111-1", estado_revision="RECIBIDO")
        self.crear_postulacion(pendiente)
        rechazado = crear_socio("Club Postulante", rut="22222222-2", estado_revision="RECHAZADO")
        self.crear_postulacion(rechazado, estado="RECHAZADA")
        aprobado = crear_socio("Centro Aprobado", rut="33333333-3", estado_revision="APROBADO")
        self.crear_postulacion(aprobado, estado="APROBADA")
        provisional = crear_socio("Grupo del Equipo", estado_revision="RECIBIDO", es_provisional=True)

        response = self.client.get(reverse("socios:lista_coordinador"))

        listados = {socio.nombre_organizacion for socio in response.context["socios"]}
        self.assertIn(aprobado.nombre_organizacion, listados)
        self.assertNotIn(provisional.nombre_organizacion, listados)
        self.assertNotIn(pendiente.nombre_organizacion, listados)
        self.assertNotIn(rechazado.nombre_organizacion, listados)

        # El propuesto por un equipo se revisa en su pestaña de Postulaciones.
        propuestos = self.client.get(reverse("socios:lista_postulaciones"), {"origen": "equipos"})
        self.assertEqual([s.nombre_organizacion for s in propuestos.context["propuestos"]], ["Grupo del Equipo"])

    def test_revisar_socio_propuesto_corrige_datos_y_decide(self):
        socio = crear_socio("grupo vecinal", estado_revision="RECIBIDO", es_provisional=True)
        url = reverse("socios:revisar_socio_propuesto", args=[socio.id])
        self.assertEqual(self.client.get(url).status_code, 200)

        # Guardar sin decidir solo corrige los datos.
        self.client.post(url, {"nombre_organizacion": "Grupo Vecinal Sur", "rut": "",
                               "contacto_nombre": "Ana Soto", "contacto_correo": "ana@grupo.cl"})
        socio.refresh_from_db()
        self.assertEqual(socio.nombre_organizacion, "Grupo Vecinal Sur")
        self.assertEqual(socio.estado_revision, "RECIBIDO")
        self.assertEqual(socio.contactos.get().correo, "ana@grupo.cl")
        self.assertTrue(AuditoriaCambio.objects.filter(entidad="SocioComunitario", accion="EDICION_SOCIO").exists())

        self.client.post(url, {"nombre_organizacion": "Grupo Vecinal Sur", "contacto_nombre": "Ana Soto",
                               "decision": "habilitar"})
        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "APROBADO")
        self.assertFalse(socio.es_provisional)
        self.assertEqual(socio.contactos.count(), 1)

    def test_socio_propuesto_solo_en_historial_del_equipo(self):
        socio = crear_socio("Club Barrio", estado_revision="RECIBIDO", es_provisional=True)
        self.client.post(reverse("socios:revisar_socio_propuesto", args=[socio.id]),
                         {"nombre_organizacion": "Club Barrio", "decision": "solo_equipo"})
        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "APROBADO")
        self.assertTrue(socio.es_provisional)
        self.assertNotIn(socio, list(socios_views.socios_disponibles()))

    def test_filtro_de_comuna_solo_trae_comunas_con_socios(self):
        con_socio = Comuna.objects.create(nombre="Lo Prado", region="Metropolitana", activo=True)
        sin_socio = Comuna.objects.create(nombre="Lo Espejo", region="Metropolitana", activo=True)
        crear_socio("Junta Lo Prado", rut="44444444-4", estado_revision="APROBADO", comuna=con_socio)

        response = self.client.get(reverse("socios:lista_coordinador"))

        self.assertIn(con_socio, response.context["comunas"])
        self.assertNotIn(sin_socio, response.context["comunas"])

    def test_rechazo_desde_catalogo_exige_motivo_y_envia_correo(self):
        socio = crear_socio("Grupo Provisional", estado_revision="RECIBIDO", es_provisional=True)
        ContactoSocio.objects.create(
            socio=socio, nombre="Ana", correo="ana@grupo.cl", es_principal=True, activo=True,
        )

        response = self.cambiar(socio, "RECHAZADO", es_provisional="1")
        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "RECIBIDO")
        self.assertContains(response, "motivo")

        self.cambiar(socio, "RECHAZADO", es_provisional="1", motivo="Datos de contacto no verificables.")
        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "RECHAZADO")
        cambio = historial_estados_socio(socio).get()
        self.assertEqual(cambio.usuario, self.coordinador)
        self.assertEqual(cambio.valores_nuevos_json["motivo_rechazo"], "Datos de contacto no verificables.")
        correo = EnvioCorreo.objects.get(destinatario="ana@grupo.cl")
        self.assertIn("Datos de contacto no verificables.", correo.cuerpo)
        self.assertIn("próxima convocatoria", correo.cuerpo)

    def test_ficha_muestra_cambios_de_estado(self):
        socio = crear_socio("Centro Disponible", estado_revision="DISPONIBLE")

        self.cambiar(socio, "TRABAJO_TERMINADO")

        socio.refresh_from_db()
        self.assertEqual(socio.estado_revision, "TRABAJO_TERMINADO")
        response = self.client.get(reverse("socios:detalle_historial", args=[socio.id]))
        self.assertContains(response, "Cambios de estado")
        self.assertContains(response, "Disponible → Trabajo terminado")
        self.assertContains(response, self.coordinador.username)

    def test_sin_cambios_no_crea_historial(self):
        socio = crear_socio("Centro Disponible", estado_revision="DISPONIBLE")

        self.cambiar(socio, "DISPONIBLE")

        self.assertFalse(historial_estados_socio(socio).exists())


# ---------------------------------------------------------------------------
# Asociación socio <-> equipo con ParticipacionSocio como fuente de verdad
# (RN-09, RF-EQP-08, RF-SC-04, RF-SC-06, RF-IND-02, RF-MIG-02)
# ---------------------------------------------------------------------------

import importlib
import threading
import unittest
import uuid as uuid_lib
from datetime import date, datetime
from unittest import mock

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from academico.models import (
    Asignatura,
    Campus,
    Carrera,
    Docente,
    Facultad,
    PeriodoAcademico,
    Seccion,
    SeccionCarrera,
    SeccionDocente,
    Sede,
)
from proyectos.models import EnlaceRegistroEquipo, Equipo
from cartas.models import SolicitudCarta
from rutas.models import RutaActividad, RutaPlantilla, RutaVersion, SeccionActividad, SeccionRuta
from socios import services as socios_services
from socios.constantes import ORIGEN_HISTORICO, ORIGEN_OPERATIVO
from socios.models import ParticipacionSocio

migracion_participaciones = importlib.import_module(
    "socios.migrations.0005_reconstruir_participaciones_equipos"
)


def crear_contexto_academico(sufijo="1", carreras=1):
    sede = Sede.objects.create(nombre=f"Sede {sufijo}", activo=True)
    campus = Campus.objects.create(sede=sede, nombre=f"Campus {sufijo}", activo=True)
    periodo = PeriodoAcademico.objects.create(
        anio=2026, tipo="SEMESTRE", nombre=f"Periodo {sufijo}", estado="Activo",
    )
    asignatura = Asignatura.objects.create(codigo=f"AS-{sufijo}", nombre="Asignatura A+S", activo=True)
    seccion = Seccion.objects.create(
        periodo=periodo, campus=campus, asignatura=asignatura,
        nrc=f"NRC-{sufijo}", seccion="1", estado="ACTIVA",
    )
    facultad = Facultad.objects.create(nombre=f"Facultad {sufijo}", activo=True)
    lista_carreras = []
    for i in range(carreras):
        carrera = Carrera.objects.create(facultad=facultad, nombre=f"Carrera {sufijo}-{i}", activo=True)
        SeccionCarrera.objects.create(seccion=seccion, carrera=carrera)
        lista_carreras.append(carrera)
    return seccion, lista_carreras


def crear_equipo(seccion, numero=1):
    return Equipo.objects.create(
        seccion=seccion, numero_grupo=numero,
        informante_nombre="Estudiante Test", informante_correo=f"e{numero}@cloud.uautonoma.cl",
        estado="Registrado",
    )


def crear_docente(seccion, username="docente_part"):
    usuario = User.objects.create_user(username=username, password="clave-de-prueba")
    usuario.groups.add(Group.objects.get_or_create(name="Docente")[0])
    docente = Docente.objects.create(
        usuario=usuario, rut="11111111-1", nombres="Docente",
        apellidos="Prueba", correo_institucional=f"{username}@uautonoma.cl", activo=True,
    )
    SeccionDocente.objects.create(seccion=seccion, docente=docente, tipo_contrato="TEST", capacitado_as=True)
    return usuario, docente


def abiertas(equipo):
    return ParticipacionSocio.objects.filter(equipo=equipo, fecha_fin__isnull=True)


class ServicioAsociacionSocioTests(TestCase):
    def setUp(self):
        self.seccion, (self.carrera,) = crear_contexto_academico("S")
        self.usuario_docente, self.docente = crear_docente(self.seccion)
        self.socio_a = crear_socio("Org A")
        self.socio_b = crear_socio("Org B")
        self.equipo = crear_equipo(self.seccion)

    def test_primera_asociacion_crea_participacion_abierta_con_contexto(self):
        participacion, creada = socios_services.asociar_socio_a_equipo(
            equipo=self.equipo, socio=self.socio_a, docente=self.docente,
        )

        self.assertTrue(creada)
        self.assertIsNone(participacion.fecha_fin)
        self.assertEqual(participacion.fecha_inicio, timezone.localdate())
        self.assertEqual(participacion.origen, ORIGEN_OPERATIVO)
        self.assertEqual(participacion.seccion, self.seccion)
        self.assertEqual(participacion.asignatura, self.seccion.asignatura)
        self.assertEqual(participacion.periodo, self.seccion.periodo)
        self.assertEqual(participacion.campus, self.seccion.campus)
        self.assertEqual(participacion.sede, self.seccion.campus.sede)
        self.assertEqual(participacion.carrera, self.carrera)
        self.assertEqual(self.equipo.socio_vigente, self.socio_a)
        self.assertEqual(Equipo.objects.get(pk=self.equipo.pk).socio_vigente, self.socio_a)

    def test_cambio_cierra_la_anterior_y_abre_otra(self):
        socios_services.asociar_socio_a_equipo(equipo=self.equipo, socio=self.socio_a, docente=self.docente)
        nueva, creada = socios_services.asociar_socio_a_equipo(
            equipo=self.equipo, socio=self.socio_b, docente=self.docente, motivo="Cambio de foco",
        )

        self.assertTrue(creada)
        anterior = ParticipacionSocio.objects.get(equipo=self.equipo, socio=self.socio_a)
        self.assertEqual(anterior.fecha_fin, timezone.localdate())
        self.assertEqual(list(abiertas(self.equipo)), [nueva])
        self.assertEqual(nueva.socio, self.socio_b)

        auditoria = AuditoriaCambio.objects.filter(
            entidad="Equipo", entidad_id=str(self.equipo.pk), accion="CAMBIO_SOCIO_EQUIPO",
        ).latest("id")
        # La auditoría guarda todo lo que tenía el antiguo HistorialSocioEquipo.
        self.assertEqual(auditoria.valores_anteriores_json["socio_comunitario_id"], self.socio_a.pk)
        self.assertEqual(auditoria.valores_anteriores_json["socio_nombre"], "Org A")
        self.assertEqual(auditoria.valores_nuevos_json["socio_comunitario_id"], self.socio_b.pk)
        self.assertEqual(auditoria.valores_nuevos_json["socio_nombre"], "Org B")
        self.assertEqual(auditoria.valores_nuevos_json["motivo"], "Cambio de foco")
        self.assertEqual(auditoria.valores_nuevos_json["docente_id"], self.docente.pk)
        self.assertEqual(auditoria.valores_nuevos_json["docente_nombre"], "Docente Prueba")

        cambio = socios_services.historial_socios_equipo(self.equipo)[0]
        self.assertEqual((cambio.socio_anterior, cambio.socio_nuevo), (self.socio_a, self.socio_b))
        self.assertEqual(cambio.cambiado_por_docente, self.docente)
        self.assertEqual(cambio.motivo, "Cambio de foco")

    def test_mismo_socio_no_duplica(self):
        socios_services.asociar_socio_a_equipo(equipo=self.equipo, socio=self.socio_a, docente=self.docente)
        _, creada = socios_services.asociar_socio_a_equipo(
            equipo=self.equipo, socio=self.socio_a, docente=self.docente,
        )

        self.assertFalse(creada)
        self.assertEqual(ParticipacionSocio.objects.filter(equipo=self.equipo).count(), 1)
        self.assertEqual(len(socios_services.historial_socios_equipo(self.equipo)), 1)

    def test_volver_a_un_socio_anterior_abre_otra_participacion(self):
        for socio in (self.socio_a, self.socio_b, self.socio_a):
            socios_services.asociar_socio_a_equipo(equipo=self.equipo, socio=socio, docente=self.docente)

        self.assertEqual(ParticipacionSocio.objects.filter(equipo=self.equipo).count(), 3)
        self.assertEqual(abiertas(self.equipo).get().socio, self.socio_a)

    def test_carrera_solo_si_la_seccion_tiene_una(self):
        seccion, _ = crear_contexto_academico("DOS", carreras=2)
        equipo = crear_equipo(seccion)

        participacion, _ = socios_services.asociar_socio_a_equipo(equipo=equipo, socio=self.socio_a)

        self.assertIsNone(participacion.carrera)
        self.assertEqual(participacion.sede, seccion.campus.sede)

    def test_error_de_integridad_se_informa_como_validacion(self):
        with mock.patch.object(
            socios_services.ParticipacionSocio.objects, "create", side_effect=IntegrityError("uq"),
        ):
            with self.assertRaises(ValidationError):
                socios_services.asociar_socio_a_equipo(equipo=self.equipo, socio=self.socio_a)

        self.assertFalse(ParticipacionSocio.objects.exists())
        self.assertFalse(AuditoriaCambio.objects.filter(entidad="Equipo").exists())
        self.assertIsNone(Equipo.objects.get(pk=self.equipo.pk).socio_vigente)

    def test_socio_vigente_usa_la_precarga_sin_consultas_extra(self):
        otro = crear_equipo(self.seccion, numero=2)
        socios_services.asociar_socio_a_equipo(equipo=self.equipo, socio=self.socio_a)
        socios_services.asociar_socio_a_equipo(equipo=self.equipo, socio=self.socio_b)

        equipos = list(Equipo.objects.filter(seccion=self.seccion).con_socio_vigente().order_by("numero_grupo"))

        with self.assertNumQueries(0):
            self.assertEqual([e.socio_vigente for e in equipos], [self.socio_b, None])
        self.assertIsNone(otro.socio_vigente)


class RestriccionesParticipacionSocioTests(TestCase):
    """Restricciones de BD (se ejecutan también en PostgreSQL)."""

    def setUp(self):
        self.seccion, _ = crear_contexto_academico("R")
        self.equipo = crear_equipo(self.seccion)
        self.socio_a = crear_socio("Org A")
        self.socio_b = crear_socio("Org B")

    def test_bd_rechaza_dos_participaciones_abiertas_del_mismo_equipo(self):
        ParticipacionSocio.objects.create(socio=self.socio_a, equipo=self.equipo, origen=ORIGEN_OPERATIVO)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ParticipacionSocio.objects.create(socio=self.socio_b, equipo=self.equipo, origen=ORIGEN_OPERATIVO)

    def test_bd_admite_varias_cerradas_del_mismo_equipo(self):
        for socio in (self.socio_a, self.socio_b):
            ParticipacionSocio.objects.create(
                socio=socio, equipo=self.equipo, origen=ORIGEN_OPERATIVO,
                fecha_inicio=date(2026, 3, 1), fecha_fin=date(2026, 4, 1),
            )
        ParticipacionSocio.objects.create(socio=self.socio_a, equipo=self.equipo, origen=ORIGEN_OPERATIVO)
        self.assertEqual(self.equipo.participaciones_socios.count(), 3)

    def test_participacion_historica_sin_equipo_ni_proyecto(self):
        ParticipacionSocio.objects.create(socio=self.socio_a, origen=ORIGEN_HISTORICO, fecha_inicio=date(2019, 3, 1))
        ParticipacionSocio.objects.create(socio=self.socio_a, origen=ORIGEN_HISTORICO, fecha_inicio=date(2020, 3, 1))

        self.assertEqual(
            ParticipacionSocio.objects.filter(equipo__isnull=True, proyecto__isnull=True).count(), 2,
        )

    def test_bd_rechaza_fecha_fin_anterior_a_inicio(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ParticipacionSocio.objects.create(
                    socio=self.socio_a, origen=ORIGEN_HISTORICO,
                    fecha_inicio=date(2026, 5, 1), fecha_fin=date(2026, 4, 1),
                )


class VistasAsociacionSocioTests(TestCase):
    def setUp(self):
        self.seccion, _ = crear_contexto_academico("V")
        self.usuario_docente, self.docente = crear_docente(self.seccion)
        self.socio_a = crear_socio("Org A", estado_revision="DISPONIBLE")
        self.socio_b = crear_socio("Org B", estado_revision="DISPONIBLE")
        self.client.force_login(self.usuario_docente)

    def _actividad_ruta(self):
        plantilla = RutaPlantilla.objects.create(nombre="Ruta", activo=True)
        version = RutaVersion.objects.create(plantilla=plantilla, numero_version=1, estado="BORRADOR")
        ruta = SeccionRuta.objects.create(seccion=self.seccion, ruta_version=version, estado="EN_PROGRESO", porcentaje_final=0)
        actividad = RutaActividad.objects.create(
            ruta_version=version, etapa="Etapa", nombre="Asociar socio", es_obligatoria=True, orden=13,
            recurso_url="/socios/ruta/actividad/{actividad}/asociar-socio/",
        )
        version.estado = "ACTIVA"
        version.save(update_fields=["estado"])
        return SeccionActividad.objects.create(seccion_ruta=ruta, ruta_actividad=actividad, estado="PENDIENTE")

    def test_gestionar_equipo_usa_el_servicio(self):
        equipo = crear_equipo(self.seccion)
        socios_services.asociar_socio_a_equipo(equipo=equipo, socio=self.socio_a)
        url = reverse("proyectos:gestionar_equipo", args=[equipo.id])

        with mock.patch(
            "proyectos.views.asociar_socio_a_equipo", wraps=socios_services.asociar_socio_a_equipo,
        ) as servicio:
            self.client.post(url, {
                "accion": "cambiar_socio", "socio_comunitario": self.socio_b.id, "motivo": "Nuevo socio",
            })

        servicio.assert_called_once()
        self.assertEqual(servicio.call_args.kwargs["docente"], self.docente)
        self.assertEqual(abiertas(equipo).get().socio, self.socio_b)
        self.assertEqual(ParticipacionSocio.objects.get(equipo=equipo, socio=self.socio_a).fecha_fin, timezone.localdate())
        response = self.client.get(url)
        self.assertEqual(len(response.context["participaciones_socio"]), 2)
        self.assertContains(response, "Vigente")
        # Historial de cambios (desde auditoría) con las mismas columnas.
        historial = response.context["historial_socios"]
        self.assertEqual(len(historial), 1)  # la asociación inicial no la hizo un docente
        self.assertEqual(historial[0].socio_nuevo, self.socio_b)
        self.assertEqual(historial[0].socio_anterior, self.socio_a)
        self.assertContains(response, "Nuevo socio")
        self.assertEqual(historial[0].cambiado_por_docente, self.docente)
        self.assertContains(response, "Socio actualmente asociado")
        self.assertEqual(response.context["equipo"].socio_vigente, self.socio_b)

    def test_gestionar_equipo_mantiene_motivo_obligatorio(self):
        equipo = crear_equipo(self.seccion)
        socios_services.asociar_socio_a_equipo(equipo=equipo, socio=self.socio_a)

        self.client.post(reverse("proyectos:gestionar_equipo", args=[equipo.id]), {
            "accion": "cambiar_socio", "socio_comunitario": self.socio_b.id, "motivo": "",
        })

        self.assertEqual(abiertas(equipo).get().socio, self.socio_a)

    def test_gestionar_equipo_mismo_socio_no_duplica(self):
        equipo = crear_equipo(self.seccion)
        socios_services.asociar_socio_a_equipo(equipo=equipo, socio=self.socio_a)

        response = self.client.post(reverse("proyectos:gestionar_equipo", args=[equipo.id]), {
            "accion": "cambiar_socio", "socio_comunitario": self.socio_a.id, "motivo": "Igual",
        }, follow=True)

        self.assertContains(response, "ya se encuentra asociado")
        self.assertEqual(ParticipacionSocio.objects.filter(equipo=equipo).count(), 1)

    def test_asociar_desde_ruta_usa_el_servicio_con_motivo_opcional(self):
        equipo = crear_equipo(self.seccion)
        actividad = self._actividad_ruta()
        url = reverse("socios:asociar_socio_equipo", args=[actividad.id])

        with mock.patch(
            "socios.services.asociar_socio_a_equipo", wraps=socios_services.asociar_socio_a_equipo,
        ) as servicio:
            self.client.post(url, {"equipo": equipo.id, "socio": self.socio_a.id})
            self.client.post(url, {"equipo": equipo.id, "socio": self.socio_b.id, "motivo": "Cambio"})
            response = self.client.post(url, {"equipo": equipo.id, "socio": self.socio_b.id}, follow=True)

        self.assertEqual(servicio.call_count, 3)
        self.assertContains(response, "ya tiene asociado")
        self.assertEqual(ParticipacionSocio.objects.filter(equipo=equipo).count(), 2)
        self.assertEqual(abiertas(equipo).get().socio, self.socio_b)
        primera = AuditoriaCambio.objects.filter(entidad="Equipo", entidad_id=str(equipo.pk)).earliest("id")
        self.assertIsNone(primera.valores_anteriores_json["socio_comunitario_id"])
        self.assertIsNone(primera.valores_nuevos_json["motivo"])
        self.assertEqual(primera.valores_nuevos_json["docente_id"], self.docente.pk)

    def test_asociar_desde_ruta_valida_largo_del_motivo(self):
        equipo = crear_equipo(self.seccion)
        actividad = self._actividad_ruta()
        url = reverse("socios:asociar_socio_equipo", args=[actividad.id])

        response = self.client.post(url, {"equipo": equipo.id, "socio": self.socio_a.id, "motivo": "x" * 256})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no puede superar los 255 caracteres")
        self.assertFalse(ParticipacionSocio.objects.filter(equipo=equipo).exists())

        self.client.post(url, {"equipo": equipo.id, "socio": self.socio_a.id, "motivo": "x" * 255})
        self.assertEqual(abiertas(equipo).get().socio, self.socio_a)

    def test_asociar_desde_ruta_muestra_socio_actual(self):
        equipo = crear_equipo(self.seccion)
        socios_services.asociar_socio_a_equipo(equipo=equipo, socio=self.socio_a)
        actividad = self._actividad_ruta()

        response = self.client.get(reverse("socios:asociar_socio_equipo", args=[actividad.id]))

        self.assertContains(response, "- Actual: Org A")


class RegistroEquipoParticipacionTests(TestCase):
    def setUp(self):
        self.seccion, _ = crear_contexto_academico("REG")
        _, self.docente = crear_docente(self.seccion)
        self.estudiante = User.objects.create_user(
            username="estudiante_part", password="clave-de-prueba",
            email="estudiante.part@cloud.uautonoma.cl",
            correo_institucional="estudiante.part@cloud.uautonoma.cl",
        )
        self.estudiante.groups.add(Group.objects.get_or_create(name="Estudiante")[0])
        enlace = EnlaceRegistroEquipo.objects.create(
            seccion=self.seccion, creado_por_docente=self.docente,
            fecha_inicio=timezone.now(), fecha_expiracion=timezone.now() + timedelta(days=7), activo=True,
        )
        self.url = reverse("proyectos:acceso_registro_equipos", kwargs={"token": enlace.token})
        self.client.force_login(self.estudiante)

    def _datos(self, **extra):
        datos = {
            "clave_idempotencia": str(uuid_lib.uuid4()),
            "cantidad_integrantes": "1",
            "rut_1": "12.345.678-5",
            "nombres_1": "Estudiante",
            "apellidos_1": "Prueba",
            "correo_1": self.estudiante.correo_institucional,
        }
        datos.update(extra)
        return datos

    def test_registro_con_socio_existente_crea_participacion_abierta(self):
        socio = crear_socio("Org Catálogo", estado_revision="DISPONIBLE")

        self.client.post(self.url, self._datos(tipo_socio="existente", socio_comunitario=socio.id))

        equipo = Equipo.objects.get(seccion=self.seccion)
        participacion = abiertas(equipo).get()
        self.assertEqual(participacion.socio, socio)
        self.assertEqual(participacion.origen, ORIGEN_OPERATIVO)
        self.assertEqual(participacion.seccion, self.seccion)
        self.assertEqual(equipo.socio_vigente, socio)
        auditoria = AuditoriaCambio.objects.get(entidad="Equipo", entidad_id=str(equipo.pk))
        self.assertEqual(auditoria.usuario, self.estudiante)
        self.assertIsNone(auditoria.valores_anteriores_json["socio_comunitario_id"])
        self.assertIsNone(auditoria.valores_nuevos_json["docente_id"])
        # Como antes, el registro estudiantil no aparece en el historial de cambios del docente.
        self.assertEqual(socios_services.historial_socios_equipo(equipo), [])

    def test_registro_con_socio_provisional_sigue_funcionando(self):
        self.client.post(self.url, self._datos(
            tipo_socio="provisional", socio_provisional_nombre="Junta Provisional",
        ))

        equipo = Equipo.objects.get(seccion=self.seccion)
        socio = SocioComunitario.objects.get(nombre_organizacion="Junta Provisional")
        self.assertTrue(socio.es_provisional)
        self.assertEqual(socio.estado_revision, "RECIBIDO")
        self.assertEqual(equipo.socio_vigente, socio)
        self.assertEqual(abiertas(equipo).get().socio, socio)

    def test_si_falla_la_asociacion_no_queda_equipo_a_medias(self):
        socio = crear_socio("Org Catálogo", estado_revision="DISPONIBLE")

        with mock.patch(
            "proyectos.views.asociar_socio_a_equipo",
            side_effect=ValidationError("No fue posible actualizar la asociación."),
        ):
            response = self.client.post(self.url, self._datos(tipo_socio="existente", socio_comunitario=socio.id))

        self.assertEqual(response.status_code, 200)
        self.assertIn("No fue posible actualizar la asociación.", response.context["errores"])
        self.assertFalse(Equipo.objects.filter(seccion=self.seccion).exists())


class FichaEIndicadoresParticipacionTests(DatosBase):
    def setUp(self):
        self.client.force_login(self.coordinador)
        self.seccion, _ = crear_contexto_academico("IND")

    def test_organizaciones_unicas_frente_a_participaciones(self):
        # RF-IND-02 CA1: participa tres veces = 1 organización, 3 participaciones.
        for anio in (2019, 2020, 2021):
            ParticipacionSocio.objects.create(
                socio=self.esperanza, origen=ORIGEN_HISTORICO, fecha_inicio=date(anio, 3, 1),
            )

        response = self.client.get(reverse("socios:lista_coordinador"), {"q": "Esperanza"})

        self.assertEqual(response.context["total_organizaciones_con_participacion"], 1)
        self.assertEqual(response.context["total_participaciones"], 3)

    def test_ficha_muestra_participaciones_reales(self):
        equipo = crear_equipo(self.seccion)
        socios_services.asociar_socio_a_equipo(equipo=equipo, socio=self.esperanza)

        response = self.client.get(reverse("socios:detalle_historial", args=[self.esperanza.id]))

        self.assertEqual(len(response.context["participaciones"]), 1)
        self.assertContains(response, "Vigente")
        self.assertContains(response, self.seccion.asignatura.nombre)


class LectoresSocioVigenteTests(TestCase):
    """Las pantallas que mostraban Equipo.socio_comunitario muestran el socio vigente."""

    def setUp(self):
        self.seccion, _ = crear_contexto_academico("LEC")
        self.usuario_docente, self.docente = crear_docente(self.seccion)
        self.socio_a = crear_socio("Org A", estado_revision="DISPONIBLE")
        self.socio_b = crear_socio("Org B", estado_revision="DISPONIBLE")
        self.equipo = crear_equipo(self.seccion)
        socios_services.asociar_socio_a_equipo(equipo=self.equipo, socio=self.socio_a)
        socios_services.asociar_socio_a_equipo(equipo=self.equipo, socio=self.socio_b, docente=self.docente)
        self.sin_socio = crear_equipo(self.seccion, numero=2)

    def _ruta(self):
        plantilla = RutaPlantilla.objects.create(nombre="Ruta", activo=True)
        version = RutaVersion.objects.create(plantilla=plantilla, numero_version=1, estado="ACTIVA")
        return SeccionRuta.objects.create(seccion=self.seccion, ruta_version=version, estado="EN_PROGRESO", porcentaje_final=0)

    def _datos_carta(self, equipo):
        return {
            "equipo": equipo.id, "institucion_receptora": "Municipalidad",
            "persona_receptora": "Persona", "cargo_receptor": "", "consideraciones": "",
        }

    def test_carta_toma_el_socio_vigente_del_equipo(self):
        self._ruta()
        self.client.force_login(self.usuario_docente)

        self.client.post(reverse("cartas:solicitar_carta_docente", args=[self.seccion.id]), self._datos_carta(self.equipo))
        self.client.post(reverse("cartas:solicitar_carta_docente", args=[self.seccion.id]), self._datos_carta(self.sin_socio))

        self.assertEqual(SolicitudCarta.objects.get(equipo=self.equipo).socio, self.socio_b)
        self.assertIsNone(SolicitudCarta.objects.get(equipo=self.sin_socio).socio)

    def test_carta_corregida_toma_el_socio_vigente(self):
        self._ruta()
        self.client.force_login(self.usuario_docente)
        self.client.post(reverse("cartas:solicitar_carta_docente", args=[self.seccion.id]), self._datos_carta(self.sin_socio))
        solicitud = SolicitudCarta.objects.get()
        SolicitudCarta.objects.filter(pk=solicitud.pk).update(estado="OBSERVADA")

        self.client.post(reverse("cartas:editar_solicitud_docente", args=[solicitud.id]), self._datos_carta(self.equipo))

        solicitud.refresh_from_db()
        self.assertEqual((solicitud.equipo, solicitud.socio, solicitud.estado), (self.equipo, self.socio_b, "PENDIENTE"))

    def test_detalle_seccion_coordinador_muestra_socio_vigente(self):
        coordinador = User.objects.create_user(username="coord_lec", password="clave-de-prueba")
        coordinador.groups.add(Group.objects.get_or_create(name="Coordinador")[0])
        self.client.force_login(coordinador)

        response = self.client.get(reverse("core:detalle_seccion", args=[self.seccion.id]))

        self.assertEqual([e.socio_vigente for e in response.context["equipos"]], [self.socio_b, None])
        self.assertContains(response, "Org B")
        self.assertNotContains(response, "Org A")
        self.assertContains(response, "Sin Socio Comunitario")

    def test_lista_de_equipos_del_docente_muestra_socio_vigente(self):
        self.client.force_login(self.usuario_docente)

        response = self.client.get(reverse("proyectos:gestionar_equipos_seccion", args=[self.seccion.id]))

        self.assertContains(response, "Org B")
        self.assertNotContains(response, "Org A")

    def test_gestionar_equipo_muestra_socio_e_historial_desde_auditoria(self):
        self.client.force_login(self.usuario_docente)

        response = self.client.get(reverse("proyectos:gestionar_equipo", args=[self.equipo.id]))

        self.assertEqual(response.context["equipo"].socio_vigente, self.socio_b)
        filas = response.context["historial_socios"]
        self.assertEqual(len(filas), 1)
        self.assertEqual((filas[0].socio_anterior, filas[0].socio_nuevo), (self.socio_a, self.socio_b))
        self.assertEqual(filas[0].cambiado_por_docente, self.docente)
        self.assertContains(response, "Historial de cambios de Socio Comunitario")

    def test_historial_conserva_nombres_si_ya_no_existe_el_docente(self):
        AuditoriaCambio.objects.filter(entidad="Equipo", entidad_id=str(self.equipo.pk), valores_nuevos_json__docente_id=self.docente.pk).update(
            valores_nuevos_json={"socio_comunitario_id": self.socio_b.pk, "socio_nombre": "Org B",
                                 "motivo": "M", "docente_id": 999999, "docente_nombre": "Docente Antiguo"},
        )

        fila = socios_services.historial_socios_equipo(self.equipo)[0]

        self.assertEqual(fila.cambiado_por_docente.nombres, "Docente Antiguo")
        self.assertEqual(fila.motivo, "M")


# Estado del esquema justo antes de socios.0005 / proyectos.0005: Equipo aún
# tiene socio_comunitario y existe HistorialSocioEquipo.
ESTADO_ANTERIOR = [
    ("socios", "0004_participacionsocio_equipo_opcional_restricciones"),
    ("proyectos", "0004_historialsocioequipo"),
]


class MigracionReconstruirParticipacionesTests(TransactionTestCase):
    """
    socios.0005 (reconstruye participaciones y copia el historial a
    auditoría) y proyectos.0005 (quita Equipo.socio_comunitario y
    HistorialSocioEquipo), sobre el esquema anterior real (MigrationExecutor).
    """

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(ESTADO_ANTERIOR)
        # Mismo estado histórico que recibe la RunPython al migrar.
        self.apps_antiguas = executor.loader.project_state(
            ("socios", "0005_reconstruir_participaciones_equipos"), at_end=False,
        ).apps
        self.EquipoAntiguo = self.apps_antiguas.get_model("proyectos", "Equipo")
        self.Historial = self.apps_antiguas.get_model("proyectos", "HistorialSocioEquipo")

        self.seccion, (self.carrera,) = crear_contexto_academico("MIG")
        self.seccion_dos, _ = crear_contexto_academico("MIG2", carreras=2)
        self.usuario_docente, self.docente = crear_docente(self.seccion)
        self.a = crear_socio("Org A")
        self.b = crear_socio("Org B")
        self.c = crear_socio("Org C")

    def tearDown(self):
        self.migrar_hasta_el_final()

    def migrar_hasta_el_final(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _fecha(self, d, hora=12):
        return timezone.make_aware(datetime(d.year, d.month, d.day, hora, 30))

    def equipo_antiguo(self, seccion, numero=1, socio=None):
        return self.EquipoAntiguo.objects.create(
            seccion_id=seccion.pk, numero_grupo=numero, socio_comunitario_id=socio.pk if socio else None,
            informante_nombre="Estudiante Test", informante_correo=f"e{numero}@cloud.uautonoma.cl",
            estado="Registrado",
        )

    def _evento(self, equipo, anterior, nuevo, cuando, motivo=None):
        evento = self.Historial.objects.create(
            equipo_id=equipo.pk, socio_anterior_id=anterior.pk if anterior else None,
            socio_nuevo_id=nuevo.pk if nuevo else None,
            cambiado_por_docente_id=self.docente.pk, motivo=motivo,
        )
        self.Historial.objects.filter(pk=evento.pk).update(fecha_cambio=self._fecha(cuando))
        return evento

    def _registrado(self, equipo, cuando):
        self.EquipoAntiguo.objects.filter(pk=equipo.pk).update(fecha_registro=self._fecha(cuando))

    def ejecutar(self):
        # La función RunPython de socios.0005 con el estado histórico.
        migracion_participaciones.reconstruir_participaciones(self.apps_antiguas, None)

    def test_reconstruye_cadena_y_vigente(self):
        equipo = self.equipo_antiguo(self.seccion, socio=self.c)
        self._registrado(equipo, date(2026, 3, 1))
        self._evento(equipo, self.a, self.b, date(2026, 4, 10), motivo="Primero")
        self._evento(equipo, self.b, self.c, date(2026, 5, 20))

        self.ejecutar()

        periodos = list(
            ParticipacionSocio.objects.filter(equipo_id=equipo.pk)
            .order_by("fecha_inicio")
            .values_list("socio_id", "fecha_inicio", "fecha_fin", "origen")
        )
        self.assertEqual(periodos, [
            (self.a.pk, date(2026, 3, 1), date(2026, 4, 10), ORIGEN_OPERATIVO),
            (self.b.pk, date(2026, 4, 10), date(2026, 5, 20), ORIGEN_OPERATIVO),
            (self.c.pk, date(2026, 5, 20), None, ORIGEN_OPERATIVO),
        ])
        vigente = abiertas(equipo.pk).get()
        self.assertEqual(vigente.carrera, self.carrera)
        self.assertEqual(vigente.sede, self.seccion.campus.sede)
        self.assertEqual(vigente.periodo, self.seccion.periodo)
        auditorias = AuditoriaCambio.objects.filter(
            entidad="Equipo", entidad_id=str(equipo.pk), accion="CAMBIO_SOCIO_EQUIPO",
        )
        self.assertEqual(auditorias.count(), 2)
        primera = auditorias.get(valores_nuevos_json__motivo="Primero")
        self.assertEqual(primera.usuario, self.usuario_docente)
        self.assertEqual(primera.fecha, self._fecha(date(2026, 4, 10)))
        self.assertEqual(primera.valores_anteriores_json["socio_nombre"], "Org A")
        self.assertEqual(primera.valores_nuevos_json["socio_nombre"], "Org B")
        self.assertEqual(primera.valores_nuevos_json["docente_id"], self.docente.pk)
        self.assertEqual(primera.valores_nuevos_json["docente_nombre"], "Docente Prueba")

    def test_equipo_sin_historial_usa_fecha_de_registro(self):
        equipo = self.equipo_antiguo(self.seccion_dos, socio=self.a)
        self._registrado(equipo, date(2026, 3, 15))

        self.ejecutar()

        vigente = abiertas(equipo.pk).get()
        self.assertEqual((vigente.socio, vigente.fecha_inicio), (self.a, date(2026, 3, 15)))
        self.assertIsNone(vigente.carrera)  # sección con dos carreras

    def test_usa_la_fecha_local_del_cambio(self):
        equipo = self.equipo_antiguo(self.seccion, socio=self.b)
        self.EquipoAntiguo.objects.filter(pk=equipo.pk).update(fecha_registro=self._fecha(date(2026, 3, 1), hora=23))
        evento = self._evento(equipo, self.a, self.b, date(2026, 4, 1))
        self.Historial.objects.filter(pk=evento.pk).update(fecha_cambio=self._fecha(date(2026, 4, 1), hora=23))

        self.ejecutar()

        cerrada = ParticipacionSocio.objects.get(equipo_id=equipo.pk, socio=self.a)
        self.assertEqual((cerrada.fecha_inicio, cerrada.fecha_fin), (date(2026, 3, 1), date(2026, 4, 1)))

    def test_no_inventa_participaciones_sin_socio_anterior(self):
        equipo = self.equipo_antiguo(self.seccion, socio=self.b)
        self._registrado(equipo, date(2026, 3, 1))
        self._evento(equipo, None, self.b, date(2026, 4, 1))

        self.ejecutar()

        self.assertEqual(
            list(ParticipacionSocio.objects.filter(equipo_id=equipo.pk).values_list("socio_id", "fecha_inicio", "fecha_fin")),
            [(self.b.pk, date(2026, 4, 1), None)],
        )

    def test_cadena_rota_deja_inicio_vacio(self):
        equipo = self.equipo_antiguo(self.seccion, socio=self.c)
        self._registrado(equipo, date(2026, 3, 1))
        self._evento(equipo, self.a, self.b, date(2026, 4, 1))
        self._evento(equipo, self.c, self.c, date(2026, 5, 1))  # el anterior no coincide con el previo

        self.ejecutar()

        rota = ParticipacionSocio.objects.get(equipo_id=equipo.pk, fecha_fin=date(2026, 5, 1))
        self.assertIsNone(rota.fecha_inicio)

    def test_es_idempotente_y_respeta_lo_existente(self):
        equipo = self.equipo_antiguo(self.seccion, socio=self.b)
        self._evento(equipo, self.a, self.b, date(2026, 4, 1))
        otro = self.equipo_antiguo(self.seccion, numero=2, socio=self.a)
        ParticipacionSocio.objects.create(socio=self.a, equipo_id=otro.pk, origen=ORIGEN_OPERATIVO)  # ya tiene

        self.ejecutar()
        self.ejecutar()

        self.assertEqual(ParticipacionSocio.objects.filter(equipo_id=equipo.pk).count(), 2)
        self.assertEqual(ParticipacionSocio.objects.filter(equipo_id=otro.pk).count(), 1)
        self.assertEqual(
            AuditoriaCambio.objects.filter(entidad="Equipo", accion="CAMBIO_SOCIO_EQUIPO", entidad_id=str(equipo.pk)).count(),
            1,
        )

    def test_cadena_completa_quita_columna_y_tabla_sin_perder_datos(self):
        equipo = self.equipo_antiguo(self.seccion, socio=self.b)
        self._registrado(equipo, date(2026, 3, 1))
        self._evento(equipo, self.a, self.b, date(2026, 4, 10), motivo="Cambio de foco")
        sin_socio = self.equipo_antiguo(self.seccion, numero=2)

        self.migrar_hasta_el_final()

        # Esquema final: sin columna ni tabla heredadas.
        with connection.cursor() as cursor:
            columnas = [c.name for c in connection.introspection.get_table_description(cursor, "proyectos_equipo")]
            tablas = connection.introspection.table_names(cursor)
        self.assertNotIn("socio_comunitario_id", columnas)
        self.assertNotIn("proyectos_historialsocioequipo", tablas)

        # Datos: participaciones y auditoría antes de borrar.
        self.assertEqual(
            list(ParticipacionSocio.objects.filter(equipo_id=equipo.pk).order_by("fecha_inicio").values_list("socio_id", "fecha_fin")),
            [(self.a.pk, date(2026, 4, 10)), (self.b.pk, None)],
        )
        actual = Equipo.objects.get(pk=equipo.pk)
        self.assertEqual(actual.socio_vigente, self.b)
        self.assertIsNone(Equipo.objects.get(pk=sin_socio.pk).socio_vigente)

        # La pantalla del docente muestra el mismo historial (fecha, socios, docente, motivo).
        self.client.force_login(self.usuario_docente)
        response = self.client.get(reverse("proyectos:gestionar_equipo", args=[equipo.pk]))
        self.assertEqual(response.status_code, 200)
        fila = response.context["historial_socios"][0]
        self.assertEqual((fila.socio_anterior, fila.socio_nuevo), (self.a, self.b))
        self.assertEqual(fila.cambiado_por_docente, self.docente)
        self.assertEqual(fila.motivo, "Cambio de foco")
        self.assertEqual(fila.fecha_cambio, self._fecha(date(2026, 4, 10)))
        self.assertContains(response, "Cambio de foco")
        self.assertContains(response, "10/04/2026")

        # Reversa de proyectos.0005: repone la columna desde la participación abierta.
        executor = MigrationExecutor(connection)
        executor.migrate([("proyectos", "0004_historialsocioequipo")])
        apps_revertidas = executor.loader.project_state([("proyectos", "0004_historialsocioequipo")]).apps
        EquipoRevertido = apps_revertidas.get_model("proyectos", "Equipo")
        self.assertEqual(EquipoRevertido.objects.get(pk=equipo.pk).socio_comunitario_id, self.b.pk)
        self.assertIsNone(EquipoRevertido.objects.get(pk=sin_socio.pk).socio_comunitario_id)


@unittest.skipUnless(connection.vendor == "postgresql", "La concurrencia real solo se prueba en PostgreSQL.")
class ConcurrenciaAsociacionPostgresTests(TransactionTestCase):
    def test_cambios_simultaneos_dejan_una_sola_participacion_abierta(self):
        seccion, _ = crear_contexto_academico("CONC")
        equipo = crear_equipo(seccion)
        socios = [crear_socio(f"Org {i}") for i in range(4)]
        barrera = threading.Barrier(len(socios))
        errores = []

        def asociar(socio):
            try:
                barrera.wait()
                socios_services.asociar_socio_a_equipo(equipo=Equipo.objects.get(pk=equipo.pk), socio=socio)
            except Exception as error:  # pragma: no cover - se informa abajo
                errores.append(error)
            finally:
                connection.close()

        hilos = [threading.Thread(target=asociar, args=(socio,)) for socio in socios]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

        self.assertEqual(errores, [])
        self.assertEqual(abiertas(equipo).count(), 1)
        self.assertEqual(ParticipacionSocio.objects.filter(equipo=equipo).count(), len(socios))
