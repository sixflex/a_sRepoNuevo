"""
Escritura uniforme de nombres de personas (RF-EQP-05: "normalizar la
escritura de los nombres").

"juan PÉREZ  de la fuente" -> "Juan Pérez de la Fuente". Solo para nombres
de personas: los de organizaciones se dejan como los escribieron (siglas
como ONG, CESFAM o JJVV) y solo se les quitan los espacios repetidos.
"""

PARTICULAS = {"de", "del", "la", "las", "los", "y", "e", "da", "van", "von"}


def _palabra(palabra, primera):
    if not primera and palabra.lower() in PARTICULAS:
        return palabra.lower()

    for separador in ("-", "'"):
        if separador in palabra:
            return separador.join(_palabra(p, True) for p in palabra.split(separador))
    return palabra[:1].upper() + palabra[1:].lower()


def nombre_persona(texto):
    palabras = str(texto or "").split()
    return " ".join(_palabra(p, i == 0) for i, p in enumerate(palabras))
