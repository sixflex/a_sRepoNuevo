"""
Opciones de los campos de texto de Gestión académica.

Los modelos guardan estos valores como texto libre (sin choices) y la base
de datos no se modifica: estas listas solo alimentan los select de los
formularios y las validaciones de las vistas. Al editar, un valor antiguo
que no esté en la lista se conserva (opciones_con_actual / opcion_valida).
"""

TIPOS_UNIDAD_ACADEMICA = [
    ("Dirección de Carrera", "Dirección de Carrera"),
    ("Secretaría de Estudios", "Secretaría de Estudios"),
    ("Escuela", "Escuela"),
    ("Departamento", "Departamento"),
]

# RF-ACA-01 CA1: el tipo es la duración del período; la temporada va en
# el nombre ("Primavera 2026"). Los registros con "Primer/Segundo semestre"
# pasaron a "Semestral" (migración academico 0003).
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

# Parte del año que cubre el período, según su tipo. No se guarda aparte:
# arma el nombre que se muestra en todo el portal, para que siempre diga en
# qué semestre, trimestre o bimestre se sitúa ("Primavera 2026 (2º semestre)",
# "2º trimestre 2026"). Cada opción es (etiqueta, plantilla del nombre).
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

# Estado con que la consolidación de planificaciones crea las secciones y
# que cuenta el panel del coordinador. Los "Activo" antiguos pasaron a
# "Activa" (migración academico 0004).
SECCION_ACTIVA = "Activa"

# Listas de la planilla oficial de planificación (hoja «Listas»).
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

# Palabras que no aportan inicial al sugerir el código de una facultad o
# carrera ("Facultad de Ingeniería" -> "INGE").
PALABRAS_SIN_INICIAL = {
    "de", "del", "la", "las", "el", "los", "y", "e", "en", "para", "con",
    "a", "al", "facultad", "carrera",
}

# Largo máximo del código sugerido (sin contar el sufijo 2, 3...).
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
