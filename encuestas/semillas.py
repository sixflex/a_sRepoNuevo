"""
Carga de formularios a partir de una definición escrita en Python (HU-09).

Sirve para traer al portal los forms que el cliente ya usa en Microsoft Forms
(knowledge/Forms preguntas.txt). Cada formulario se describe en
encuestas/definiciones/ con las funciones seccion(), pregunta() y opcion(), y
crear_formulario() lo guarda como una versión en borrador.

Las condiciones se escriben con la clave de una pregunta anterior y los textos
(o valores) de sus opciones:

    pregunta("Semestre", c.ALTERNATIVA_UNICA, ["Otoño", "Primavera"], clave="semestre")
    seccion("Asignaturas Otoño", [...], si=("semestre", ["Otoño"]))
"""

from django.db import transaction
from django.utils import timezone

from academico.models import Carrera

from . import constantes as c
from . import services
from .models import (
    BloqueFormulario,
    FormularioPlantilla,
    FormularioVersion,
    OpcionPregunta,
    PreguntaFormulario,
)


def seccion(titulo, preguntas, descripcion="", si=None):
    return {"titulo": titulo, "descripcion": descripcion, "si": si, "preguntas": preguntas}


def pregunta(texto, tipo, opciones=(), obligatoria=True, clave=None, **config):
    return {
        "texto": texto, "tipo": tipo, "opciones": list(opciones),
        "obligatoria": obligatoria, "clave": clave, "config": config,
    }


def opcion(texto, valor=None, otras=False, solo_si=None, carrera=None):
    """Opción con algo más que su texto: «Otros» con texto, valor fijo, condición o carrera."""
    return {"texto": texto, "valor": valor, "otras": otras, "solo_si": solo_si, "carrera": carrera}


def otras(texto="Otras"):
    """La opción «Otras» con campo de texto de Microsoft Forms."""
    return opcion(texto, otras=True)


class _Claves:
    """Preguntas ya creadas que pueden usarse en una condición."""

    def __init__(self):
        self.preguntas = {}

    def guardar(self, clave, pregunta_creada, valores_por_texto):
        self.preguntas[clave] = (pregunta_creada, valores_por_texto)

    def regla(self, condicion):
        if not condicion:
            return None
        clave, respuestas = condicion
        if clave not in self.preguntas:
            raise ValueError(f"La condición usa «{clave}», que no es una pregunta anterior con clave.")
        pregunta_creada, valores_por_texto = self.preguntas[clave]
        valores = []
        for respuesta in respuestas:
            valor = valores_por_texto.get(respuesta, respuesta)
            if valor not in valores_por_texto.values():
                raise ValueError(f"«{respuesta}» no es una opción de «{clave}».")
            valores.append(valor)
        return {"pregunta": pregunta_creada.id, "valores": valores}


def _crear_opciones(pregunta_creada, opciones, claves):
    usados = set()
    valores_por_texto = {}
    reglas_opciones = {}
    datos_opciones = {}
    for orden, datos in enumerate(opciones, start=1):
        if isinstance(datos, str):
            datos = opcion(datos)
        valor = datos["valor"] or services.valor_desde_texto(datos["texto"], usados)
        usados.add(valor)
        OpcionPregunta.objects.create(
            pregunta=pregunta_creada, texto=datos["texto"], valor=valor,
            orden=orden, es_otras=datos["otras"],
        )
        valores_por_texto[datos["texto"]] = valor
        if datos["solo_si"]:
            reglas_opciones[valor] = claves.regla(datos["solo_si"])
        if datos["carrera"]:
            carrera = Carrera.objects.filter(nombre__icontains=datos["carrera"]).order_by("id").first()
            if carrera:
                datos_opciones[valor] = {"carrera_id": carrera.id}
    config = dict(pregunta_creada.configuracion_json or {})
    if reglas_opciones:
        config["visibilidad_opciones"] = reglas_opciones
    if datos_opciones:
        config["opciones"] = datos_opciones
    if config != (pregunta_creada.configuracion_json or {}):
        pregunta_creada.configuracion_json = config
        pregunta_creada.save(update_fields=["configuracion_json"])
    return valores_por_texto


@transaction.atomic
def crear_formulario(definicion):
    """
    Crea el formulario en borrador y devuelve su versión. Si ya existe un
    formulario con el mismo código, no hace nada y devuelve None.
    """
    if FormularioPlantilla.objects.filter(codigo=definicion["codigo"]).exists():
        return None
    plantilla = FormularioPlantilla.objects.create(
        codigo=definicion["codigo"],
        titulo=definicion["titulo"],
        descripcion=definicion.get("descripcion") or None,
        proceso=definicion["proceso"],
        activo=True,
    )
    version = FormularioVersion.objects.create(
        plantilla=plantilla,
        numero_version=1,
        estado=c.BORRADOR,
        contexto_tipo=definicion.get("contexto_tipo"),
        fecha_creacion=timezone.now(),
    )
    claves = _Claves()
    for orden_bloque, datos_seccion in enumerate(definicion["secciones"], start=1):
        bloque = BloqueFormulario.objects.create(
            formulario_version=version,
            titulo=datos_seccion["titulo"],
            descripcion=datos_seccion["descripcion"] or None,
            orden=orden_bloque,
            regla_visibilidad_json=claves.regla(datos_seccion["si"]),
        )
        for orden, datos in enumerate(datos_seccion["preguntas"], start=1):
            pregunta_creada = PreguntaFormulario.objects.create(
                version=version,
                bloque=bloque,
                texto=datos["texto"],
                tipo=datos["tipo"],
                obligatoria=datos["obligatoria"],
                orden=orden,
                configuracion_json=dict(datos["config"]) or None,
            )
            valores = _crear_opciones(pregunta_creada, datos["opciones"], claves)
            if datos["clave"]:
                claves.guardar(datos["clave"], pregunta_creada, valores)
    services.validar_orden_condiciones(version)
    return version


def contar(definicion):
    """Cantidad de secciones y preguntas, para el mensaje del comando."""
    return len(definicion["secciones"]), sum(len(s["preguntas"]) for s in definicion["secciones"])
