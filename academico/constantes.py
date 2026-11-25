TIPOS_UNIDAD_ACADEMICA = [
    ("Dirección de Carrera", "Dirección de Carrera"),
    ("Secretaría de Estudios", "Secretaría de Estudios"),
    ("Escuela", "Escuela"),
    ("Departamento", "Departamento"),
]

TIPOS_PERIODO = [
    ("Anual", "Anual"),
    ("Semestral", "Semestral"),
    ("Trimestral", "Trimestral"),
    ("Bimestral", "Bimestral"),
]

ESTADOS_PERIODO = [
    ("Planificado", "Planificado"),
    ("Activo", "Activo"),
    ("Finalizado", "Finalizado"),
]

ORDINALES = ["1er", "2º", "3er", "4º", "5º", "6º"]

PARTES_PERIODO = {
    "Anual": [
        ("Año completo", "Anual {anio}"),
    ],
    "Semestral": [
        ("Otoño (1er semestre)", "Otoño {anio} (1er semestre)"),
        ("Primavera (2º semestre)", "Primavera {anio} (2º semestre)"),
    ],
    "Trimestral": [
        (f"{ordinal} trimestre", f"{ordinal} trimestre {{anio}}")
        for ordinal in ORDINALES[:4]
    ],
    "Bimestral": [
        (f"{ordinal} bimestre", f"{ordinal} bimestre {{anio}}")
        for ordinal in ORDINALES
    ],
}


def nombre_periodo(tipo, parte, anio):
    """Nombre sugerido para la parte elegida, o "" si no corresponde al tipo."""
    for etiqueta, plantilla in PARTES_PERIODO.get(tipo, []):
        if etiqueta == parte:
            return plantilla.format(anio=anio).strip()
    return ""


ESTADOS_SECCION = [
    ("Planificada", "Planificada"),
    ("Activa", "Activa"),
    ("Finalizada", "Finalizada"),
]




SECCION_ACTIVA = "Activa"


JORNADAS = [
    ("Diurna", "Diurna"),
    ("Vespertina TECH", "Vespertina TECH"),
    ("Advance", "Advance"),
]

TIPOS_CONTRATO = [
    ("Regular", "Regular"),
    ("Adjunto", "Adjunto"),
]

NIVELES = [(str(nivel), str(nivel)) for nivel in range(1, 16)]



PALABRAS_SIN_INICIAL = {
    "de", "del", "la", "las", "el", "los", "y", "e", "en", "para", "con",
    "a", "al", "facultad", "carrera",
}


LARGO_CODIGO_SUGERIDO = 8


def opciones_con_actual(opciones, actual):
    """
    Agrega el valor guardado si no está en la lista, para que al editar un
    registro antiguo el select lo muestre y no se pierda.
    """
    if actual and actual not in dict(opciones):
        return opciones + [(actual, actual)]

    return opciones


def opcion_valida(valor, opciones, guardado=None):
    """Valor de la lista, o el mismo que ya tenía el registro."""
    return bool(valor) and (valor in dict(opciones) or valor == guardado)
