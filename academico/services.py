"""
Códigos de Facultad y Carrera, y aviso de nombres repetidos.

Ningún dato de la universidad trae código de facultad ni de carrera, así
que el portal sugiere uno a partir del nombre (editable en el formulario)
y lo genera al guardar si se deja vacío. El código de asignatura y el NRC
son institucionales: solo se normalizan, nunca se inventan.
"""

import re
import unicodedata

from . import constantes


def _ascii(texto):
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()


def nombre_repetido(registros, nombre, excluir_pk=None):
    """
    ¿Otro registro ya usa este nombre, sin distinguir mayúsculas, tildes ni
    espacios extra? Se compara en Python (son decenas de registros) porque
    en SQLite iexact solo ignora mayúsculas en letras sin tilde.
    """
    def clave(texto):
        return " ".join(_ascii(texto).casefold().split())

    buscado = clave(nombre)
    return any(
        clave(otro) == buscado
        for otro in registros.exclude(pk=excluir_pk).values_list("nombre", flat=True)
    )


def normalizar_codigo(valor):
    """Mayúsculas y sin espacios: " inf 101 " -> "INF101"."""
    return "".join((valor or "").split()).upper()


def sugerir_codigo(nombre):
    """
    Iniciales de las palabras con significado, en mayúsculas y sin tildes:
    "Ingeniería Civil Informática" -> "ICI". Si queda una sola palabra se
    usan sus 4 primeras letras: "Derecho" -> "DERE".
    """
    texto = _ascii(nombre).upper()
    palabras = [
        palabra
        for palabra in re.findall(r"[A-Z0-9]+", texto)
        if palabra.lower() not in constantes.PALABRAS_SIN_INICIAL
    ]

    if not palabras:
        return ""

    if len(palabras) == 1:
        sigla = palabras[0][:4]
    else:
        sigla = "".join(palabra[0] for palabra in palabras)

    return sigla[:constantes.LARGO_CODIGO_SUGERIDO]


def codigo_unico(modelo, nombre, excluir_pk=None):
    """Código sugerido que no use otro registro; si choca, agrega 2, 3..."""
    base = sugerir_codigo(nombre)

    if not base:
        return None

    otros = modelo.objects.exclude(pk=excluir_pk)
    codigo = base
    sufijo = 2

    while otros.filter(codigo__iexact=codigo).exists():
        codigo = f"{base}{sufijo}"
        sufijo += 1

    return codigo
