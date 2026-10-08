import shutil
import tempfile
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.http import QueryDict
from django.test import TestCase, override_settings
from django.urls import reverse

from academico.models import Asignatura, Campus, Carrera, Facultad, PeriodoAcademico, Sede, Seccion

from . import constantes as c
from . import services
from .forms import RespuestaFormularioForm
from .models import (
    BloqueFormulario,
    EnlaceFormulario,
    FormularioPlantilla,
    OpcionPregunta,
    PreguntaFormulario,
    RespuestaFormulario,
)

RUT_VALIDO = "11.111.111-1"
OTRO_RUT_VALIDO = "12345678-5"


def como_post(datos):
    """El formulario lee los valores como en un POST real (QueryDict)."""
    query = QueryDict(mutable=True)
    for clave, valor in datos.items():
        query.setlist(clave, valor if isinstance(valor, list) else [valor])
    return query


def crear_pregunta(version, bloque, texto, tipo, obligatoria=False, opciones=(), config=None, regla=None):
    pregunta = PreguntaFormulario.objects.create(
        version=version,
        bloque=bloque,
        texto=texto,
        tipo=tipo,
        obligatoria=obligatoria,
        orden=services.siguiente_orden(version.preguntas.filter(bloque=bloque)),
        configuracion_json=config,
        regla_visibilidad_json=regla,
    )
    for orden, (valor, texto_opcion, es_otras) in enumerate(opciones, start=1):
        OpcionPregunta.objects.create(
            pregunta=pregunta, texto=texto_opcion, valor=valor, orden=orden, es_otras=es_otras,
        )
    return pregunta


class FormularioBaseTestCase(TestCase):
    """
    Formulario con pestañas de dos programas (A y B):
    - una pregunta común con RUT,
    - una sección y una pregunta obligatoria que solo aplican a A,
    - una alternativa con una opción solo para B y otra "Otras".
    """

    def setUp(self):
        User = get_user_model()
        self.coordinador = User.objects.create_user(username="coord_enc", password="Clave1234")
        self.coordinador.groups.add(Group.objects.create(name="Coordinador"))
        self.docente = User.objects.create_user(username="docente_enc", password="Clave1234")
        self.docente.groups.add(Group.objects.create(name="Docente"))

        facultad = Facultad.objects.create(codigo="FAN", nombre="Administración y Negocios", activo=True)
        self.carrera_a = Carrera.objects.create(
            facultad=facultad, codigo="ICO", nombre="Ingeniería Comercial", activo=True,
        )

        self.version = services.crear_formulario("Ficha de prueba", usuario=self.coordinador)
        self.bloque_comun = self.version.bloques.get()
        self.selector = crear_pregunta(
            self.version, self.bloque_comun, "Programa", c.SELECTOR_PROGRAMA, obligatoria=True,
            opciones=[("A", "Programa A", False), ("B", "Programa B", False)],
            config={"opciones": {"A": {"carrera_id": self.carrera_a.id}}},
        )
        self.rut = crear_pregunta(
            self.version, self.bloque_comun, "RUT", c.RUT, obligatoria=True,
            config={"dato_respondente": "rut"},
        )
        self.personas = crear_pregunta(
            self.version, self.bloque_comun, "Personas", c.ALTERNATIVA_UNICA, obligatoria=True,
            opciones=[("UNO", "Solo yo", False), ("DOS", "Dos", False), ("OTRAS", "Otras", True)],
            config={"visibilidad_opciones": {"OTRAS": {"pregunta": self.selector.id, "valores": ["B"]}}},
        )
        self.bloque_a = BloqueFormulario.objects.create(
            formulario_version=self.version, titulo="Solo A", orden=2,
            regla_visibilidad_json={"pregunta": self.selector.id, "valores": ["A"]},
        )
        self.solo_a = crear_pregunta(
            self.version, self.bloque_a, "Pregunta de A", c.TEXTO_CORTO, obligatoria=True,
        )
        self.enlace = services.publicar(self.version, self.coordinador)
        self.url_responder = reverse("encuestas:responder", args=[self.enlace.token])

    def datos(self, programa="A", **extra):
        datos = {
            f"p{self.selector.id}": programa,
            f"p{self.rut.id}": RUT_VALIDO,
            f"p{self.personas.id}": "DOS",
            f"p{self.solo_a.id}": "Respuesta A",
            "clave_envio": extra.pop("clave_envio", "clave-1"),
        }
        datos.update(extra)
        return datos

    def formulario(self, datos):
        self.version.refresh_from_db()
        bloques, preguntas = services.cargar_estructura(self.version)
        return RespuestaFormularioForm(self.version, bloques, preguntas, como_post(datos))


class VisibilidadTests(FormularioBaseTestCase):
    """CDE-102 y CDE-103: secciones, preguntas y opciones según el programa."""

    def test_seccion_de_otro_programa_no_se_muestra(self):
        bloques, preguntas = services.cargar_estructura(self.version)
        visibles_b = services.calcular_visibilidad(bloques, preguntas, {self.selector.id: {"B"}})
        self.assertNotIn(self.bloque_a.id, visibles_b[0])
        self.assertNotIn(self.solo_a.id, visibles_b[1])

        visibles_a = services.calcular_visibilidad(bloques, preguntas, {self.selector.id: {"A"}})
        self.assertIn(self.bloque_a.id, visibles_a[0])
        self.assertIn(self.solo_a.id, visibles_a[1])

    def test_sin_programa_elegido_no_se_muestra_la_seccion_condicionada(self):
        bloques, preguntas = services.cargar_estructura(self.version)
        bloques_visibles, _, _ = services.calcular_visibilidad(bloques, preguntas, {})
        self.assertIn(self.bloque_comun.id, bloques_visibles)
        self.assertNotIn(self.bloque_a.id, bloques_visibles)

    def test_opcion_limitada_a_un_programa(self):
        bloques, preguntas = services.cargar_estructura(self.version)
        _, _, opciones_a = services.calcular_visibilidad(bloques, preguntas, {self.selector.id: {"A"}})
        _, _, opciones_b = services.calcular_visibilidad(bloques, preguntas, {self.selector.id: {"B"}})
        self.assertNotIn("OTRAS", {o.valor for o in opciones_a[self.personas.id]})
        self.assertIn("OTRAS", {o.valor for o in opciones_b[self.personas.id]})

    def test_obligatoria_oculta_no_bloquea_el_envio(self):
        form = self.formulario(self.datos("B", **{f"p{self.solo_a.id}": ""}))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn(self.solo_a.id, form.valores)

    def test_obligatoria_visible_se_exige(self):
        form = self.formulario(self.datos("A", **{f"p{self.solo_a.id}": ""}))
        self.assertFalse(form.is_valid())
        self.assertIn(f"p{self.solo_a.id}", form.errors)

    def test_respuesta_a_pregunta_oculta_se_descarta(self):
        form = self.formulario(self.datos("B", **{f"p{self.solo_a.id}": "no corresponde"}))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn(self.solo_a.id, form.valores)

    def test_opcion_de_otro_programa_es_rechazada(self):
        form = self.formulario(self.datos("A", **{f"p{self.personas.id}": "OTRAS", f"p{self.personas.id}_otro": "x"}))
        self.assertFalse(form.is_valid())
        self.assertIn(f"p{self.personas.id}", form.errors)

    def test_opcion_otras_exige_detalle(self):
        form = self.formulario(self.datos("B", **{f"p{self.personas.id}": "OTRAS"}))
        self.assertFalse(form.is_valid())

        form = self.formulario(self.datos("B", **{f"p{self.personas.id}": "OTRAS", f"p{self.personas.id}_otro": "5 personas"}))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.otros[self.personas.id], "5 personas")

    def test_rut_invalido(self):
        form = self.formulario(self.datos("A", **{f"p{self.rut.id}": "11111111-2"}))
        self.assertFalse(form.is_valid())
        self.assertIn(f"p{self.rut.id}", form.errors)


class TiposDePreguntaTests(TestCase):
    """CDE-101: cada tipo se valida y se guarda en su columna."""

    def setUp(self):
        self.version = services.crear_formulario("Tipos")
        bloque = self.version.bloques.get()
        self.p = {
            tipo: crear_pregunta(self.version, bloque, tipo, tipo, config=config, opciones=opciones)
            for tipo, config, opciones in [
                (c.TEXTO_LARGO, None, ()),
                (c.NUMERO, {"minimo": 0, "maximo": 100}, ()),
                (c.FECHA, None, ()),
                (c.CORREO, None, ()),
                (c.LISTA, None, [("X", "Equis", False), ("Y", "I griega", False)]),
                (c.SELECCION_MULTIPLE, {"max_marcadas": 2}, [("1", "Uno", False), ("2", "Dos", False), ("3", "Tres", False)]),
                (c.ESCALA, {"minimo": 1, "maximo": 5, "estilo": "estrellas"}, ()),
            ]
        }
        services.publicar(self.version)

    def form(self, datos):
        bloques, preguntas = services.cargar_estructura(self.version)
        return RespuestaFormularioForm(self.version, bloques, preguntas, como_post(datos)), preguntas

    def campo(self, tipo):
        return f"p{self.p[tipo].id}"

    def test_valores_validos_se_guardan(self):
        form, preguntas = self.form({
            self.campo(c.TEXTO_LARGO): "Texto largo",
            self.campo(c.NUMERO): "42",
            self.campo(c.FECHA): "2026-10-08",
            self.campo(c.CORREO): "persona@correo.cl",
            self.campo(c.LISTA): "Y",
            self.campo(c.SELECCION_MULTIPLE): ["1", "3"],
            self.campo(c.ESCALA): "4",
        })
        self.assertTrue(form.is_valid(), form.errors)
        respuesta = services.guardar_respuesta(
            self.version, preguntas, form.valores, form.otros, form.visibilidad[1], form.seleccion,
        )
        resumen = {p.tipo: texto for p, texto in services.resumen_respuesta(respuesta)}
        self.assertEqual(resumen[c.TEXTO_LARGO], "Texto largo")
        self.assertEqual(resumen[c.NUMERO], "42")
        self.assertEqual(resumen[c.FECHA], "08/10/2026")
        self.assertEqual(resumen[c.CORREO], "persona@correo.cl")
        self.assertEqual(resumen[c.LISTA], "I griega")
        self.assertEqual(resumen[c.SELECCION_MULTIPLE], "Uno, Tres")
        self.assertEqual(resumen[c.ESCALA], "4 de 5")
        self.assertEqual(respuesta.respondente_correo, "persona@correo.cl")

    def test_escala_fuera_de_rango(self):
        form, _ = self.form({self.campo(c.ESCALA): "6"})
        self.assertFalse(form.is_valid())

    def test_numero_fuera_de_rango(self):
        form, _ = self.form({self.campo(c.NUMERO): "101"})
        self.assertFalse(form.is_valid())

    def test_maximo_de_casillas(self):
        form, _ = self.form({self.campo(c.SELECCION_MULTIPLE): ["1", "2", "3"]})
        self.assertFalse(form.is_valid())

    def test_correo_invalido(self):
        form, _ = self.form({self.campo(c.CORREO): "no-es-correo"})
        self.assertFalse(form.is_valid())


class ArchivoTests(TestCase):
    def setUp(self):
        self.carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)
        self.version = services.crear_formulario("Con archivo")
        self.pregunta = crear_pregunta(
            self.version, self.version.bloques.get(), "Adjunto", c.ARCHIVO, config={"extensiones": ["pdf"]},
        )
        self.enlace = services.publicar(self.version)

    def test_archivo_permitido_se_guarda(self):
        storages = {
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            "private": {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": self.carpeta}},
        }
        with override_settings(STORAGES=storages):
            respuesta = self.client.post(reverse("encuestas:responder", args=[self.enlace.token]), {
                f"p{self.pregunta.id}": SimpleUploadedFile("carta.pdf", b"%PDF-1.4", content_type="application/pdf"),
                "clave_envio": "k",
            })
        self.assertEqual(respuesta.status_code, 302)
        guardada = RespuestaFormulario.objects.get()
        self.assertEqual(services.resumen_respuesta(guardada)[0][1], "carta.pdf")

    def test_extension_no_configurada_es_rechazada(self):
        respuesta = self.client.post(reverse("encuestas:responder", args=[self.enlace.token]), {
            f"p{self.pregunta.id}": SimpleUploadedFile("foto.png", b"png", content_type="image/png"),
            "clave_envio": "k",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(RespuestaFormulario.objects.exists())


class ResponderTests(FormularioBaseTestCase):
    """CDE-104 y CDE-106: responder por enlace, duplicados y contexto."""

    def test_formulario_publico_no_pide_sesion(self):
        respuesta = self.client.get(self.url_responder)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Programa A")

    def test_envio_guarda_respuesta_con_programa_y_carrera(self):
        respuesta = self.client.post(self.url_responder, self.datos("A"))
        self.assertRedirects(respuesta, reverse("encuestas:enviado", args=[self.enlace.token]))
        guardada = RespuestaFormulario.objects.get()
        self.assertEqual(guardada.enlace, self.enlace)
        self.assertEqual(guardada.carrera, self.carrera_a)
        self.assertEqual(guardada.respondente_rut, "11111111-1")
        textos = dict((p.id, t) for p, t in services.resumen_respuesta(guardada))
        self.assertEqual(textos[self.selector.id], "Programa A")
        self.assertEqual(textos[self.solo_a.id], "Respuesta A")

    def test_otras_guarda_el_detalle(self):
        self.client.post(self.url_responder, self.datos(
            "B", **{f"p{self.personas.id}": "OTRAS", f"p{self.personas.id}_otro": "5 personas"},
        ))
        guardada = RespuestaFormulario.objects.get()
        textos = dict((p.id, t) for p, t in services.resumen_respuesta(guardada))
        self.assertEqual(textos[self.personas.id], "Otras: 5 personas")
        self.assertNotIn(self.solo_a.id, textos)
        self.assertIsNone(guardada.carrera)

    def test_doble_envio_con_la_misma_clave_no_duplica(self):
        self.client.post(self.url_responder, self.datos("A"))
        respuesta = self.client.post(self.url_responder, self.datos("A"))
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(RespuestaFormulario.objects.count(), 1)

    def test_mismo_rut_y_programa_es_rechazado(self):
        self.client.post(self.url_responder, self.datos("A"))
        respuesta = self.client.post(self.url_responder, self.datos("A", clave_envio="clave-2"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya existe una respuesta registrada con este RUT")
        self.assertEqual(RespuestaFormulario.objects.count(), 1)

    def test_mismo_rut_en_otro_programa_es_permitido(self):
        self.client.post(self.url_responder, self.datos("A"))
        self.client.post(self.url_responder, self.datos("B", clave_envio="clave-2"))
        self.assertEqual(RespuestaFormulario.objects.count(), 2)

    def test_formulario_cerrado_muestra_aviso(self):
        services.cerrar(self.version)
        respuesta = self.client.get(self.url_responder)
        self.assertTemplateUsed(respuesta, "encuestas/cerrado.html")
        self.client.post(self.url_responder, self.datos("A"))
        self.assertFalse(RespuestaFormulario.objects.exists())

    def test_formulario_archivado_desactiva_enlace(self):
        services.cerrar(self.version)
        services.archivar(self.version)
        self.enlace.refresh_from_db()
        self.assertFalse(self.enlace.activo)
        self.assertTemplateUsed(self.client.get(self.url_responder), "encuestas/cerrado.html")

    def test_contexto_desde_enlace_de_seccion(self):
        sede = Sede.objects.create(nombre="Santiago", ciudad="Santiago", activo=True)
        campus = Campus.objects.create(sede=sede, nombre="Providencia", activo=True)
        periodo = PeriodoAcademico.objects.create(anio=2026, tipo="Primavera", nombre="Primavera 2026", estado="Activo")
        asignatura = Asignatura.objects.create(codigo="INV", nombre="Investigación de Mercados", activo=True)
        seccion = Seccion.objects.create(
            periodo=periodo, campus=campus, asignatura=asignatura,
            nrc="10001", seccion="01", jornada="Diurna", estado="Activa",
        )
        enlace = services.crear_enlace(self.version, self.coordinador, seccion=seccion)
        self.client.post(reverse("encuestas:responder", args=[enlace.token]), self.datos("A"))
        guardada = RespuestaFormulario.objects.get()
        self.assertEqual(guardada.seccion, seccion)
        self.assertEqual(guardada.campus, campus)
        self.assertEqual(guardada.sede, sede)
        self.assertEqual(guardada.periodo, periodo)
        self.assertEqual(guardada.nrc_snapshot, "10001")


class CicloDeVidaTests(FormularioBaseTestCase):
    """CDE-100 y CDE-105: estados, versiones y copia."""

    def test_version_con_respuestas_no_es_editable(self):
        self.assertTrue(services.es_editable(self.version))
        self.client.post(self.url_responder, self.datos("A"))
        self.assertFalse(services.es_editable(self.version))
        with self.assertRaises(services.FormularioNoEditable):
            services.eliminar_pregunta(self.solo_a)

    def test_nueva_version_copia_y_remapea_reglas(self):
        nueva = services.crear_nueva_version(self.version)
        self.assertEqual(nueva.numero_version, 2)
        self.assertEqual(nueva.estado, c.BORRADOR)
        selector = nueva.preguntas.get(tipo=c.SELECTOR_PROGRAMA)
        bloque_a = nueva.bloques.get(titulo="Solo A")
        personas = nueva.preguntas.get(texto="Personas")
        self.assertEqual(bloque_a.regla_visibilidad_json, {"pregunta": selector.id, "valores": ["A"]})
        self.assertEqual(
            personas.configuracion_json["visibilidad_opciones"]["OTRAS"]["pregunta"], selector.id,
        )
        self.assertEqual(selector.configuracion_json["opciones"]["A"]["carrera_id"], self.carrera_a.id)
        self.assertEqual(nueva.preguntas.count(), self.version.preguntas.count())

    def test_publicar_nueva_version_mantiene_el_enlace(self):
        nueva = services.crear_nueva_version(self.version)
        enlace = services.publicar(nueva)
        self.version.refresh_from_db()
        self.assertEqual(enlace.pk, self.enlace.pk)
        self.assertEqual(enlace.token, self.enlace.token)
        self.assertEqual(enlace.version, nueva)
        self.assertEqual(self.version.estado, c.CERRADA)

    def test_respuestas_anteriores_quedan_en_su_version(self):
        self.client.post(self.url_responder, self.datos("A"))
        nueva = services.crear_nueva_version(self.version)
        services.publicar(nueva)
        # Mismo enlace, ahora con las preguntas de la versión 2.
        ids = {p.texto: p.id for p in nueva.preguntas.all()}
        self.client.post(self.url_responder, {
            f"p{ids['Programa']}": "A",
            f"p{ids['RUT']}": OTRO_RUT_VALIDO,
            f"p{ids['Personas']}": "DOS",
            f"p{ids['Pregunta de A']}": "Respuesta A",
            "clave_envio": "otra",
        })
        self.assertEqual(self.version.respuestas.count(), 1)
        self.assertEqual(nueva.respuestas.count(), 1)

    def test_copiar_formulario_crea_otro_independiente(self):
        copia = services.copiar_formulario(self.version)
        self.assertNotEqual(copia.plantilla, self.version.plantilla)
        self.assertEqual(copia.estado, c.BORRADOR)
        self.assertEqual(copia.plantilla.titulo, "Copia de Ficha de prueba")
        self.assertEqual(copia.preguntas.count(), self.version.preguntas.count())

    def test_transiciones_invalidas(self):
        with self.assertRaises(services.TransicionInvalida):
            services.archivar(self.version)  # publicada: hay que cerrarla antes
        services.cerrar(self.version)
        with self.assertRaises(services.TransicionInvalida):
            services.cerrar(self.version)
        services.reabrir(self.version)
        self.assertEqual(self.version.estado, c.PUBLICADA)

    def test_no_se_publica_sin_preguntas(self):
        vacio = services.crear_formulario("Vacío")
        with self.assertRaises(services.TransicionInvalida):
            services.publicar(vacio)

    def test_eliminar_condicionante_quita_las_reglas(self):
        borrador = services.crear_nueva_version(self.version)
        selector = borrador.preguntas.get(tipo=c.SELECTOR_PROGRAMA)
        services.eliminar_pregunta(selector)
        self.assertIsNone(borrador.bloques.get(titulo="Solo A").regla_visibilidad_json)
        personas = borrador.preguntas.get(texto="Personas")
        self.assertNotIn("visibilidad_opciones", personas.configuracion_json or {})

    def test_mover_pregunta(self):
        services.mover(self.rut, self.version.preguntas.filter(bloque=self.bloque_comun), "arriba")
        orden = list(self.version.preguntas.filter(bloque=self.bloque_comun).order_by("orden").values_list("id", flat=True))
        self.assertEqual(orden[:2], [self.rut.id, self.selector.id])

    def test_duplicar_pregunta(self):
        copia = services.duplicar_pregunta(self.personas)
        self.assertEqual(copia.orden, self.personas.orden + 1)
        self.assertEqual(copia.opciones.count(), 3)
        with self.assertRaises(services.TransicionInvalida):
            services.duplicar_pregunta(self.selector)


class ConstructorVistasTests(FormularioBaseTestCase):
    """El Coordinador arma el formulario desde el portal, sin ayuda de TI."""

    def setUp(self):
        super().setUp()
        self.borrador = services.crear_formulario("Nuevo", usuario=self.coordinador)

    def test_solo_coordinacion_entra_al_constructor(self):
        url = reverse("encuestas:lista")
        self.assertEqual(self.client.get(url).status_code, 302)  # sin sesión: al login
        self.client.force_login(self.docente)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.coordinador)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_paginas_del_constructor_cargan(self):
        self.client.force_login(self.coordinador)
        for nombre, args in [
            ("encuestas:lista", []),
            ("encuestas:editor", [self.version.id]),
            ("encuestas:crear_pregunta", [self.borrador.id]),
            ("encuestas:editar_pregunta", [self.personas.id]),
            ("encuestas:editar_seccion", [self.bloque_a.id]),
            ("encuestas:vista_previa", [self.version.id]),
            ("encuestas:publicacion", [self.version.id]),
            ("encuestas:respuestas", [self.version.id]),
        ]:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.client.get(reverse(nombre, args=args)).status_code, 200)

    def test_nuevo_formulario_abre_el_editor_en_blanco(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(reverse("encuestas:crear"))
        plantilla = FormularioPlantilla.objects.get(titulo="Formulario sin título")
        self.assertRedirects(respuesta, reverse("encuestas:editor", args=[plantilla.versiones.get().id]))

    def test_agregar_pregunta_con_opciones_y_estrellas(self):
        self.client.force_login(self.coordinador)
        bloque = self.borrador.bloques.get()
        url = reverse("encuestas:crear_pregunta", args=[self.borrador.id])
        respuesta = self.client.post(url, {
            "texto": "¿Qué sede?", "tipo": c.LISTA, "obligatoria": "on", "bloque": bloque.id,
            "opcion_id": ["", ""], "opcion_texto": ["Santiago", "Talca"],
            "opcion_otros": ["0", "0"], "opcion_programas": ["", ""], "opcion_carrera": ["", ""],
        })
        self.assertEqual(respuesta.status_code, 302)
        lista = self.borrador.preguntas.get(texto="¿Qué sede?")
        self.assertEqual([o.texto for o in services.opciones_ordenadas(lista)], ["Santiago", "Talca"])

        self.client.post(url, {
            "texto": "Evalúe la atención", "tipo": c.ESCALA, "bloque": bloque.id,
            "minimo": "1", "maximo": "5", "estilo_escala": "estrellas",
        })
        escala = self.borrador.preguntas.get(texto="Evalúe la atención")
        self.assertEqual(escala.configuracion_json["estilo"], "estrellas")
        self.assertEqual(escala.configuracion_json["maximo"], 5)

    def test_pregunta_con_opciones_exige_al_menos_una(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(reverse("encuestas:crear_pregunta", args=[self.borrador.id]), {
            "texto": "Sin opciones", "tipo": c.ALTERNATIVA_UNICA, "bloque": self.borrador.bloques.get().id,
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(self.borrador.preguntas.exists())

    def test_editar_opciones_conserva_valores(self):
        self.client.force_login(self.coordinador)
        nueva = services.crear_nueva_version(self.version)
        personas = nueva.preguntas.get(texto="Personas")
        opciones = services.opciones_ordenadas(personas)
        self.client.post(reverse("encuestas:editar_pregunta", args=[personas.id]), {
            "texto": "Personas", "tipo": c.ALTERNATIVA_UNICA, "obligatoria": "on", "bloque": personas.bloque_id,
            "opcion_id": [str(o.id) for o in opciones] + [""],
            "opcion_texto": ["Solo yo", "Dos personas", "Otras", "Tres"],
            "opcion_otros": ["0", "0", "1", "0"],
            "opcion_programas": ["", "", "B", ""],
            "opcion_carrera": ["", "", "", ""],
        })
        personas.refresh_from_db()
        valores = [o.valor for o in services.opciones_ordenadas(personas)]
        self.assertEqual(valores[:3], ["UNO", "DOS", "OTRAS"])
        self.assertEqual(personas.opciones.get(valor="DOS").texto, "Dos personas")
        selector = nueva.preguntas.get(tipo=c.SELECTOR_PROGRAMA)
        self.assertEqual(
            personas.configuracion_json["visibilidad_opciones"],
            {"OTRAS": {"pregunta": selector.id, "valores": ["B"]}},
        )

    def test_version_con_respuestas_redirige_sin_modificar(self):
        self.client.post(self.url_responder, self.datos("A"))
        self.client.force_login(self.coordinador)
        respuesta = self.client.post(reverse("encuestas:eliminar_pregunta", args=[self.solo_a.id]))
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(PreguntaFormulario.objects.filter(pk=self.solo_a.pk).exists())

    def test_publicacion_muestra_enlace_y_qr(self):
        self.client.force_login(self.coordinador)
        respuesta = self.client.get(reverse("encuestas:publicacion", args=[self.version.id]))
        self.assertContains(respuesta, str(self.enlace.token))
        self.assertContains(respuesta, "data:image/png;base64,")

    def test_publicar_y_cerrar_desde_la_vista(self):
        self.client.force_login(self.coordinador)
        crear_pregunta(self.borrador, self.borrador.bloques.get(), "Nombre", c.TEXTO_CORTO)
        url = reverse("encuestas:publicacion", args=[self.borrador.id])
        self.client.post(url, {"accion": "publicar", "fecha_inicio_vigencia": "", "fecha_fin_vigencia": ""})
        self.borrador.refresh_from_db()
        self.assertEqual(self.borrador.estado, c.PUBLICADA)
        self.assertTrue(EnlaceFormulario.objects.filter(version=self.borrador, activo=True).exists())
        self.client.post(url, {"accion": "cerrar"})
        self.borrador.refresh_from_db()
        self.assertEqual(self.borrador.estado, c.CERRADA)


class ConstructorEnVivoTests(FormularioBaseTestCase):
    """Peticiones del editor de una sola página (encuestas_constructor.js)."""

    FETCH = {"HTTP_X_REQUESTED_WITH": "fetch"}

    def setUp(self):
        super().setUp()
        self.borrador = services.crear_nueva_version(self.version)
        self.client.force_login(self.coordinador)
        self.preguntas = {p.texto: p for p in self.borrador.preguntas.all()}

    def test_agregar_pregunta_queda_bajo_la_activa(self):
        rut = self.preguntas["RUT"]
        respuesta = self.client.post(
            reverse("encuestas:crear_pregunta", args=[self.borrador.id]),
            {"bloque": rut.bloque_id, "despues_de": rut.id}, **self.FETCH,
        )
        datos = respuesta.json()
        nueva = PreguntaFormulario.objects.get(pk=datos["id"])
        self.assertEqual(nueva.texto, c.PREGUNTA_NUEVA)
        self.assertEqual(nueva.orden, rut.orden + 1)
        self.assertEqual(nueva.opciones.count(), 1)
        self.assertIn(f'id="tarjeta-{nueva.id}"', datos["html"])
        personas = self.preguntas["Personas"]
        personas.refresh_from_db()
        self.assertEqual(personas.orden, nueva.orden + 1)

    def test_abrir_editor_devuelve_el_formulario(self):
        respuesta = self.client.get(
            reverse("encuestas:editar_pregunta", args=[self.preguntas["Personas"].id]), **self.FETCH,
        )
        self.assertIn("data-pregunta-editor", respuesta.json()["html"])

    def test_guardado_automatico_devuelve_ids_de_opciones(self):
        personas = self.preguntas["Personas"]
        url = reverse("encuestas:editar_pregunta", args=[personas.id])
        datos = {
            "texto": "Personas", "tipo": c.ALTERNATIVA_UNICA, "bloque": personas.bloque_id,
            "opcion_id": ["", ""], "opcion_texto": ["Uno", "Dos"],
            "opcion_otros": ["0", "0"], "opcion_programas": ["", ""], "opcion_carrera": ["", ""],
        }
        primera = self.client.post(url, datos, **self.FETCH).json()
        self.assertTrue(primera["ok"])
        self.assertEqual(len(primera["opciones"]), 2)
        # El siguiente guardado envía esos ids: las opciones no se recrean.
        datos["opcion_id"] = [str(i) for i in primera["opciones"]]
        datos["opcion_texto"] = ["Uno", "Dos personas"]
        segunda = self.client.post(url, datos, **self.FETCH).json()
        self.assertEqual(segunda["opciones"], primera["opciones"])

    def test_guardado_con_errores_responde_por_campo(self):
        personas = self.preguntas["Personas"]
        respuesta = self.client.post(
            reverse("encuestas:editar_pregunta", args=[personas.id]),
            {"texto": "", "tipo": c.TEXTO_CORTO, "bloque": personas.bloque_id}, **self.FETCH,
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("texto", respuesta.json()["errores"])

    def test_arrastrar_a_otra_seccion(self):
        personas = self.preguntas["Personas"]
        bloque_a = self.borrador.bloques.get(titulo="Solo A")
        ids = [personas.id, self.preguntas["Pregunta de A"].id]
        respuesta = self.client.post(
            reverse("encuestas:ordenar_preguntas", args=[self.borrador.id]),
            {"bloque": bloque_a.id, "preguntas": ids}, **self.FETCH,
        )
        self.assertTrue(respuesta.json()["ok"])
        personas.refresh_from_db()
        self.assertEqual((personas.bloque_id, personas.orden), (bloque_a.id, 1))

    def test_no_se_puede_dejar_una_condicion_antes_de_su_pregunta(self):
        # "Personas" tiene una opción que depende de "Programa": no puede quedar sobre ella.
        personas = self.preguntas["Personas"]
        url = reverse("encuestas:mover_pregunta", args=[personas.id, "arriba"])
        self.assertEqual(self.client.post(url, **self.FETCH).status_code, 200)
        respuesta = self.client.post(url, **self.FETCH)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("depende de «Programa»", respuesta.json()["error"])
        personas.refresh_from_db()
        self.assertEqual(personas.orden, 2)

    def test_agregar_seccion_bajo_la_actual(self):
        comun = self.borrador.bloques.get(orden=1)
        respuesta = self.client.post(
            reverse("encuestas:crear_seccion", args=[self.borrador.id]), {"despues_de": comun.id}, **self.FETCH,
        )
        nueva = BloqueFormulario.objects.get(pk=respuesta.json()["id"])
        self.assertEqual(nueva.orden, 2)
        self.assertEqual(self.borrador.bloques.get(titulo="Solo A").orden, 3)

    def test_version_con_respuestas_responde_409(self):
        self.client.post(self.url_responder, self.datos("A"))
        respuesta = self.client.post(
            reverse("encuestas:duplicar_pregunta", args=[self.personas.id]), **self.FETCH,
        )
        self.assertEqual(respuesta.status_code, 400)
        respuesta = self.client.get(reverse("encuestas:editar_pregunta", args=[self.personas.id]), **self.FETCH)
        self.assertEqual(respuesta.status_code, 409)


class AyudasYResumenTests(FormularioBaseTestCase):
    def test_formulario_publico_explica_el_formato_del_rut(self):
        respuesta = self.client.get(self.url_responder)
        self.assertContains(respuesta, "con o sin puntos y guion. Ejemplo: 12.345.678-5")

    def test_resumen_cuenta_opciones_y_filtra_por_programa(self):
        self.client.post(self.url_responder, self.datos("A"))
        self.client.post(self.url_responder, self.datos(
            "B", clave_envio="otra", **{f"p{self.rut.id}": OTRO_RUT_VALIDO, f"p{self.personas.id}": "UNO"},
        ))
        resumen = {f["pregunta"].id: f for f in services.estadisticas(self.version)}
        conteo = {o["texto"]: o["cantidad"] for o in resumen[self.personas.id]["opciones"]}
        self.assertEqual(conteo, {"Solo yo": 1, "Dos": 1, "Otras": 0})
        self.assertEqual(resumen[self.solo_a.id]["textos"], ["Respuesta A"])

        solo_b = {f["pregunta"].id: f for f in services.estadisticas(self.version, "B")}
        self.assertEqual(solo_b[self.personas.id]["respondidas"], 1)

        self.client.force_login(self.coordinador)
        pagina = self.client.get(reverse("encuestas:respuestas", args=[self.version.id]), {"programa": "B"})
        self.assertEqual(len(pagina.context["filas"]), 1)


class FichaEmprendedoresTests(TestCase):
    """Carga de la ficha de emprendedores con pestañas por programa."""

    def test_carga_es_idempotente_y_queda_publicada(self):
        call_command("cargar_ficha_emprendedores", stdout=StringIO())
        call_command("cargar_ficha_emprendedores", stdout=StringIO())
        plantilla = FormularioPlantilla.objects.get(codigo="FICHA_EMPRENDEDORES")
        version = plantilla.versiones.get()
        self.assertEqual(version.estado, c.PUBLICADA)
        self.assertEqual(version.preguntas.count(), 19)
        self.assertTrue(version.enlaces.filter(activo=True).exists())

    def test_cada_programa_ve_sus_preguntas(self):
        call_command("cargar_ficha_emprendedores", "--sin-publicar", stdout=StringIO())
        version = FormularioPlantilla.objects.get(codigo="FICHA_EMPRENDEDORES").versiones.get()
        self.assertEqual(version.estado, c.BORRADOR)
        bloques, preguntas = services.cargar_estructura(version)
        selector = services.pregunta_selector(preguntas)
        formalizado = next(p for p in preguntas if p.texto == "Está Formalizado?")
        antiguedad = next(p for p in preguntas if p.texto.startswith("Antiguedad"))

        _, visibles_ce, opciones_ce = services.calcular_visibilidad(
            bloques, preguntas, {selector.id: {"CONSULTORIA_EMPRESAS"}},
        )
        _, visibles_im, opciones_im = services.calcular_visibilidad(
            bloques, preguntas, {selector.id: {"INV_MERCADOS"}},
        )
        self.assertNotIn(formalizado.id, visibles_ce)
        self.assertIn(formalizado.id, visibles_im)
        self.assertNotIn("Menos de 1 año", [o.texto for o in opciones_ce[antiguedad.id]])
        self.assertIn("Menos de 1 año", [o.texto for o in opciones_im[antiguedad.id]])
