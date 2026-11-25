"""
Centros de Negocio SERCOTEC normalizados (reunión con el cliente, 2/11/2026).

El centro se escribía como texto libre ("CDN Las Condes", "STGO", "Santiago"…)
y así no se puede agrupar a los emprendedores por centro para el seguimiento
que hace SERCOTEC. Aquí está la lista cerrada que usan los formularios y la
función que lleva un texto libre al nombre oficial.

La lista sale de los centros que ya aparecen en los datos y de los que nombró
el cliente; para agregar uno basta con sumarlo aquí (no hay migración).
"""

import re
import unicodedata


PREFIJO = "Centro de Negocios Sercotec"


LUGARES = [
    "Curepto",
    "El Bosque",
    "Estación Central",
    "Independencia",
    "La Cisterna",
    "La Florida",
    "Las Cabras",
    "Las Condes",
    "Maipú",
    "Ñuñoa",
    "Pedro Aguirre Cerda",
    "San Javier",
    "San Joaquín",
    "San José de Maipo",
    "San Miguel",
    "Santiago",
    "Talca",
]

CENTROS = [f"{PREFIJO} {lugar}" for lugar in LUGARES]


OPCIONES = [(centro, centro) for centro in CENTROS]


_ABREVIATURAS = {
    "stgo": "santiago",
    "stgo centro": "santiago",
    "santiago centro": "santiago",
    "est central": "estacion central",
    "e central": "estacion central",
    "pac": "pedro aguirre cerda",
    "sjm": "san jose de maipo",
}


_RUIDO = re.compile(r"\b(centros?|de|del|negocios?|sercotec|cdn|cn|sede|oficina)\b")


def _simple(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"[^a-z0-9 ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _lugar(texto):
    lugar = re.sub(r"\s+", " ", _RUIDO.sub(" ", _simple(texto))).strip()
    return _ABREVIATURAS.get(lugar, lugar)


_POR_LUGAR = {_lugar(lugar): f"{PREFIJO} {lugar}" for lugar in LUGARES}


def normalizar_centro(texto):
    """
    Nombre oficial del centro a partir de un texto libre, o None si no se
    reconoce (por ejemplo "no estoy asociado" o un centro que no está en la lista).
    """
    return _POR_LUGAR.get(_lugar(texto)) if texto else None
