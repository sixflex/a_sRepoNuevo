"""
Estados de socios y postulaciones (RF-SC-02).

Los campos del modelo son texto libre (sin choices) y la base de datos no
se modifica: estas listas solo alimentan los select, las validaciones y
los nombres que se muestran. Los valores son los que ya se guardan hoy,
más ASIGNADO (RF-SC-02).
"""

# Ciclo de vida del socio (SocioComunitario.estado_revision)
ESTADOS_SOCIO = [
    ("RECIBIDO", "Recibido"),
    ("APROBADO", "Aprobado"),
    ("RECHAZADO", "Rechazado"),
    ("DISPONIBLE", "Disponible"),
    ("ASIGNADO", "Asignado"),
    ("TRABAJO_TERMINADO", "Trabajo terminado"),
]

# RF-SC-02: un socio aprobado pasa a Disponible, Asignado y Trabajo
# terminado. El coordinador lo mueve entre esos estados en ambos sentidos
# (p. ej. de Trabajo terminado vuelve a Disponible para otra convocatoria).
ESTADOS_SOCIO_APROBADO = ["APROBADO", "DISPONIBLE", "ASIGNADO", "TRABAJO_TERMINADO"]

TRANSICIONES_SOCIO = {
    "RECIBIDO": ["APROBADO", "RECHAZADO"],
    "RECHAZADO": ["APROBADO"],
    **{
        estado: ESTADOS_SOCIO_APROBADO + ["RECHAZADO"]
        for estado in ESTADOS_SOCIO_APROBADO
    },
}

# Estados en que el docente ve al socio en el catálogo y puede elegirlo
# (RF-SC-03). Asignado sigue visible: un socio puede trabajar con varios
# equipos (RN-09).
ESTADOS_SOCIO_SELECCIONABLES = ["APROBADO", "DISPONIBLE", "ASIGNADO"]

# Decisión sobre la postulación (PostulacionSocio.estado)
ESTADOS_POSTULACION = [
    ("RECIBIDA", "Recibida"),
    ("APROBADA", "Aprobada"),
    ("RECHAZADA", "Rechazada"),
]


def etiqueta(opciones, valor):
    return dict(opciones).get(valor, valor)


def estados_siguientes(actual):
    """
    Estados que el coordinador puede elegir para un socio, incluido el
    actual. Un estado antiguo que no está en la lista puede pasar a
    cualquiera.
    """
    if actual not in TRANSICIONES_SOCIO:
        return list(ESTADOS_SOCIO)

    permitidos = {actual, *TRANSICIONES_SOCIO[actual]}
    return [opcion for opcion in ESTADOS_SOCIO if opcion[0] in permitidos]


# Procedencia de cada ParticipacionSocio (modelo de BD: OPERATIVO / HISTORICO).
# OPERATIVO: asociación creada desde el portal (registro de equipo o cambio
# del docente). HISTORICO: carga de datos antiguos, que puede no tener
# equipo ni proyecto (RF-MIG-02).
ORIGEN_OPERATIVO = "OPERATIVO"
ORIGEN_HISTORICO = "HISTORICO"

ORIGENES_PARTICIPACION = [
    (ORIGEN_OPERATIVO, "Operativo"),
    (ORIGEN_HISTORICO, "Histórico"),
]
