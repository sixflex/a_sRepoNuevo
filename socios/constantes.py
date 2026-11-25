"""
Estados de socios y postulaciones (RF-SC-02).

Los campos del modelo son texto libre (sin choices) y la base de datos no
se modifica: estas listas solo alimentan los select, las validaciones y
los nombres que se muestran. Los valores son los que ya se guardan hoy,
más ASIGNADO (RF-SC-02).
"""


ESTADOS_SOCIO = [
    ("RECIBIDO", "Recibido"),
    ("APROBADO", "Aprobado"),
    ("RECHAZADO", "Rechazado"),
    ("DISPONIBLE", "Disponible"),
    ("ASIGNADO", "Asignado"),
    ("TRABAJO_TERMINADO", "Trabajo terminado"),
]




ESTADOS_SOCIO_APROBADO = ["APROBADO", "DISPONIBLE", "ASIGNADO", "TRABAJO_TERMINADO"]

TRANSICIONES_SOCIO = {
    "RECIBIDO": ["APROBADO", "RECHAZADO"],
    "RECHAZADO": ["APROBADO"],
    **{
        estado: ESTADOS_SOCIO_APROBADO + ["RECHAZADO"]
        for estado in ESTADOS_SOCIO_APROBADO
    },
}




ESTADOS_SOCIO_SELECCIONABLES = ["APROBADO", "DISPONIBLE", "ASIGNADO"]


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






ORIGEN_OPERATIVO = "OPERATIVO"
ORIGEN_HISTORICO = "HISTORICO"

ORIGENES_PARTICIPACION = [
    (ORIGEN_OPERATIVO, "Operativo"),
    (ORIGEN_HISTORICO, "Histórico"),
]




CLASIFICACIONES_SOCIO = [
    "Municipalidad", "Corporación", "Fundación", "Cesfam", "Colegio", "CDN Sercotec",
    "Junta de Vecinos", "Club de Adulto Mayor", "Club deportivo", "Emprendedor(a) - Pyme",
    "Universidad Autónoma", "Otras",
]
