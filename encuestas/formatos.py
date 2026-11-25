"""
Formato de las respuestas cortas (RN-17 y RNF-DAT-01: los datos se guardan
normalizados y los filtros no dependen de interpretar texto libre).

Una respuesta corta puede tener un formato:

- "comuna": se elige de la lista oficial de comunas y se guarda con su
  nombre oficial ("la florida" -> "La Florida").
- "telefono": número chileno guardado siempre igual ("+56 9 1234 5678").
- "carrera" / "asignatura": sugiere los nombres del catálogo y, si lo escrito
  coincide con uno, guarda el nombre del catálogo.

El formato se lee de la configuración de la pregunta ("formato"); si no
viene, se deduce del texto de la pregunta, así funciona también con los
formularios ya publicados y con los que cree la Coordinación sin tener que
configurar nada. "libre" lo desactiva. No cambia la base de datos.

A todas las respuestas cortas se les quitan además los espacios repetidos.
"""

import re

from django.core.exceptions import ValidationError

from socios.comunas import clave

from . import constantes as c

LIBRE = "libre"
COMUNA = "comuna"
TELEFONO = "telefono"
CARRERA = "carrera"
ASIGNATURA = "asignatura"

FORMATOS = [
    (LIBRE, "Texto libre"),
    (COMUNA, "Comuna (lista oficial)"),
    (TELEFONO, "Teléfono"),
    (CARRERA, "Carrera (sugiere las del portal)"),
    (ASIGNATURA, "Asignatura (sugiere las del portal)"),
]
CON_LISTA = {COMUNA, CARRERA, ASIGNATURA}

EJEMPLO_TELEFONO = "+56 9 1234 5678"
MENSAJE_TELEFONO = (
    "Escriba un teléfono chileno de 9 dígitos, con o sin +56. "
    f"Ejemplo: {EJEMPLO_TELEFONO}"
)


def deducir(texto_pregunta):
    """El formato que corresponde a una pregunta por su texto, o LIBRE."""
    texto = clave(texto_pregunta)
    if "comuna" in texto:
        return COMUNA
    if any(p in texto for p in ("telefono", "celular", "numero de contacto")):
        return TELEFONO
    if texto == "carrera" or texto.startswith("carrera "):
        return CARRERA
    if "asignatura" in texto:
        return ASIGNATURA
    return LIBRE


def formato(pregunta, config=None):
    if pregunta.tipo != c.TEXTO_CORTO:
        return LIBRE
    elegido = (config or {}).get("formato")
    if elegido in dict(FORMATOS):
        return elegido
    return deducir(pregunta.texto)


def ordenado(texto):
    """Sin espacios al inicio, al final ni repetidos."""
    return " ".join(str(texto or "").split())


def _un_telefono(texto):
    digitos = re.sub(r"\D", "", texto)
    if digitos.startswith("56") and len(digitos) == 11:
        digitos = digitos[2:]
    if len(digitos) != 9:
        raise ValidationError(MENSAJE_TELEFONO)
    if digitos[0] in "92":
        return f"+56 {digitos[0]} {digitos[1:5]} {digitos[5:]}"

    return f"+56 {digitos[:2]} {digitos[2:5]} {digitos[5:]}"


def telefono(texto):
    """
    "+56912345678", "9 1234 5678" o "56 9 1234-5678" -> "+56 9 1234 5678".
    Acepta más de un número separado por "/", "," o " y " (p. ej. celular y fijo).
    """
    partes = [p for p in re.split(r"\s*(?:/|,|;|\by\b|\bo\b)\s*", texto) if re.search(r"\d", p)]
    if not partes:
        raise ValidationError(MENSAJE_TELEFONO)
    return " / ".join(_un_telefono(p) for p in partes)


def opciones(nombre_formato):
    """Nombres del catálogo para la lista desplegable del formato."""
    if nombre_formato == COMUNA:
        from socios.comunas import nombres_comunas

        return nombres_comunas()
    if nombre_formato == CARRERA:
        from academico.models import Carrera

        return sorted(set(Carrera.objects.values_list("nombre", flat=True)), key=clave)
    if nombre_formato == ASIGNATURA:
        from academico.models import Asignatura

        return sorted(set(Asignatura.objects.values_list("nombre", flat=True)), key=clave)
    return []


def normalizar(nombre_formato, valor, catalogos=None):
    """
    El valor como se guarda. catalogos es {formato: [nombres]} ya leído
    (para no consultar la BD por cada pregunta). Lanza ValidationError si
    no sirve.
    """
    valor = ordenado(valor)
    if not valor or nombre_formato == LIBRE:
        return valor
    if nombre_formato == TELEFONO:
        return telefono(valor)
    nombres = (catalogos or {}).get(nombre_formato)
    if nombres is None:
        nombres = opciones(nombre_formato)
    por_clave = {clave(n): n for n in nombres}
    if clave(valor) in por_clave:
        return por_clave[clave(valor)]
    if nombre_formato == COMUNA and nombres:
        raise ValidationError("Elija una comuna de la lista (escriba las primeras letras).")
    return valor


def indicacion(nombre_formato):
    if nombre_formato == COMUNA:
        return "Escriba las primeras letras y elija la comuna de la lista."
    if nombre_formato == TELEFONO:
        return f"Ejemplo: {EJEMPLO_TELEFONO}"
    return ""
