"""
Precarga de formularios desde la sección (ficha única del proyecto A+S).

El docente ya no repite en cada formulario de la Ruta los datos que el
sistema conoce: su nombre, la asignatura, la carrera, el campus, el período,
la cantidad de grupos, etc. Se toman de la sección del enlace, de la cuenta
del docente y de los equipos registrados, y se muestran ya escritos para que
el docente solo los revise (puede cambiarlos).

No se agregan campos a la BD: la relación pregunta -> dato vive aquí, por el
código de la plantilla y el texto exacto de la pregunta, para que funcione
con cualquier versión ya publicada del formulario.
"""

import unicodedata

from . import constantes as c
from . import services

ORIGEN_CUENTA = "Desde tu cuenta"
ORIGEN_SECCION = "Desde la sección"
ORIGEN_EQUIPOS = "Equipos registrados"
ORIGEN_RESPUESTA = "De un formulario anterior"
ORIGEN_RUTA = "Según tu Ruta"

FORMULARIO_PROYECTO = "FORMULARIO_PROYECTO_AS_2026"
FORMALIZACION_ACUERDOS = "FORMALIZACION_ACUERDOS_AS_2026"
RESUMEN_IMPLEMENTACION = "RESUMEN_IMPLEMENTACION_DOCENTE"
REGISTRO_REFLEXION = "REGISTRO_REFLEXION_AS"

# código de plantilla -> {texto de la pregunta: dato}
PREGUNTAS = {
    FORMULARIO_PROYECTO: {
        "Nombre de la Asignatura": "asignatura",
        "Carrera": "carrera",
        "Cantidad de Estudiantes": "estudiantes",
        "Cantidad de grupos": "grupos",
        "Nombre del docente": "docente_nombre",
    },
    FORMALIZACION_ACUERDOS: {
        "Nombre del Docente / Profesor formador": "docente_nombre",
        "Nombre de la Asignatura": "asignatura",
        "Nombre del docente firmante": "docente_nombre",
    },
    RESUMEN_IMPLEMENTACION: {
        "Nombre Completo Docente (dos nombres y dos apellidos)": "docente_nombre",
        "RUT (en el siguiente formato 15548766-5)": "docente_rut",
        "Correo Institucional": "docente_correo",
        "Año que esta reportando": "anio",
        "Período en que se realizó la asignatura": "periodo",
        "Campus": "campus",
        "Facultad": "facultad",
        "Carrera": "carrera",
        "Nombre de la asignatura  (Tal como aparece en el programa de estudios)": "asignatura",
        "Nivel": "nivel",
        "Cantidad total de estudiantes (Si tiene más de 1 sección a su cargo, súmelas)": "estudiantes",
        "Cantidad total de socios comunitarios (Si tiene más de 1 sección a su cargo, sume los SC)": "socios",
    },
    REGISTRO_REFLEXION: {
        "¿Qué reflexión estás registrando?": "momento_reflexion",
    },
}

ORIGEN_POR_DATO = {
    "docente_nombre": ORIGEN_CUENTA,
    "docente_rut": ORIGEN_CUENTA,
    "docente_correo": ORIGEN_CUENTA,
    "grupos": ORIGEN_EQUIPOS,
    "estudiantes": ORIGEN_EQUIPOS,
    "socios": ORIGEN_EQUIPOS,
    "nivel": ORIGEN_RESPUESTA,
    "momento_reflexion": ORIGEN_RUTA,
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(texto.lower().split())


def _docente(seccion, usuario):
    perfil = getattr(usuario, "perfil_docente", None) if getattr(usuario, "is_authenticated", False) else None
    docentes = list(seccion.docentes.all())
    if perfil and any(d.pk == perfil.pk for d in docentes):
        return perfil
    return docentes[0] if docentes else perfil


def _periodo_cliente(seccion):
    """El período como lo nombra el formulario del cliente (Diurno Otoño / Primavera)."""
    nombre = _normalizar(seccion.periodo.nombre)
    if "vespertino" in _normalizar(seccion.jornada) or "advance" in _normalizar(seccion.jornada):
        return None
    if "primavera" in nombre:
        return "Diurno Primavera (segundo semestre)"
    if "otono" in nombre:
        return "Diurno Otoño (primer semestre)"
    return None


def _nivel_respondido(seccion):
    """Nivel que el docente ya escribió en el Formulario del Proyecto de esta sección."""
    from .models import RespuestaPregunta

    detalle = (
        RespuestaPregunta.objects
        .filter(
            respuesta__seccion=seccion,
            respuesta__version__plantilla__codigo=FORMULARIO_PROYECTO,
            pregunta__texto="Nivel",
        )
        .exclude(valor_texto__isnull=True).exclude(valor_texto="")
        .order_by("-respuesta__fecha_envio")
        .values_list("valor_texto", flat=True)
        .first()
    )
    return detalle.strip() if detalle else None


def _momento_reflexion(seccion):
    """La primera reflexión de la Ruta (12, 15, 17) que aún no se marca como hecha."""
    from rutas.models import SeccionActividad

    from .definiciones.registro_reflexion import MOMENTO_POR_ORDEN

    pendiente = (
        SeccionActividad.objects
        .filter(
            seccion_ruta__seccion=seccion,
            ruta_actividad__orden__in=MOMENTO_POR_ORDEN,
            completada_por_docente__isnull=True,
        )
        .order_by("ruta_actividad__orden")
        .values_list("ruta_actividad__orden", flat=True)
        .first()
    )
    return MOMENTO_POR_ORDEN.get(pendiente)


def datos_seccion(seccion, usuario=None):
    """Lo que el sistema ya sabe de la sección, listo para escribir en un formulario."""
    from django.db.models import Count

    from socios.models import ParticipacionSocio

    datos = {}
    docente = _docente(seccion, usuario)
    if docente:
        datos["docente_nombre"] = f"{docente.nombres} {docente.apellidos}".strip()
        datos["docente_rut"] = docente.rut
        datos["docente_correo"] = docente.correo_institucional

    datos["asignatura"] = seccion.asignatura.nombre
    carreras = list(seccion.carreras.select_related("facultad"))
    if carreras:
        datos["carrera"] = ", ".join(c.nombre for c in carreras)
        facultades = {c.facultad.nombre for c in carreras if c.facultad_id}
        if len(facultades) == 1:
            datos["facultad"] = facultades.pop()
    datos["campus"] = seccion.campus.nombre
    datos["anio"] = str(seccion.periodo.anio)
    periodo = _periodo_cliente(seccion)
    if periodo:
        datos["periodo"] = periodo

    equipos = seccion.equipos.annotate(n=Count("integrantes"))
    grupos = equipos.count()
    if grupos:
        datos["grupos"] = grupos
        estudiantes = sum(e.n for e in equipos)
        if estudiantes:
            datos["estudiantes"] = estudiantes
        socios = (
            ParticipacionSocio.objects.filter(equipo__seccion=seccion)
            .values("socio").distinct().count()
        )
        if socios:
            datos["socios"] = socios

    nivel = _nivel_respondido(seccion)
    if nivel:
        datos["nivel"] = nivel
    momento = _momento_reflexion(seccion)
    if momento:
        datos["momento_reflexion"] = momento
    return datos


def _valor_opcion(pregunta, valor):
    """Para listas y alternativas: la opción que corresponde al dato, o None."""
    buscado = _normalizar(valor)
    if not buscado:
        return None
    opciones = [o for o in services.opciones_ordenadas(pregunta) if not o.es_otras]
    for opcion in opciones:
        if _normalizar(opcion.texto) == buscado or _normalizar(opcion.valor) == buscado:
            return opcion.valor
    # "Campus Providencia" -> "Providencia"; "Ciencias Sociales y Humanidades" exacto ya cubierto.
    parciales = [o for o in opciones if len(_normalizar(o.texto)) > 3 and _normalizar(o.texto) in buscado]
    if len(parciales) == 1:
        return parciales[0].valor
    return None


def precargar(version, preguntas, seccion, usuario=None):
    """
    Valores iniciales para RespuestaFormularioForm y el origen de cada uno.

    Devuelve (initial, origenes): initial es {nombre_campo: valor} y
    origenes es {nombre_campo: "Desde la sección" | ...} para mostrar la
    etiqueta junto a la pregunta.
    """
    if seccion is None:
        return {}, {}
    mapa = PREGUNTAS.get(version.plantilla.codigo)
    if not mapa:
        return {}, {}

    datos = datos_seccion(seccion, usuario)
    initial, origenes = {}, {}
    for pregunta in preguntas:
        dato = mapa.get(pregunta.texto)
        if dato is None or dato not in datos:
            continue
        valor = datos[dato]
        if pregunta.tipo in (c.LISTA, c.ALTERNATIVA_UNICA):
            valor = _valor_opcion(pregunta, valor)
            if valor is None:
                continue
        elif pregunta.tipo in c.TIPOS_CON_OPCIONES:
            continue
        nombre = services.nombre_campo(pregunta)
        initial[nombre] = valor
        origenes[nombre] = ORIGEN_POR_DATO.get(dato, ORIGEN_SECCION)
    return initial, origenes
