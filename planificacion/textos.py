"""
Formatos de texto de la planilla de Dirección que se guardan en campos varchar
del modelo .mmd (sin migraciones): el horario de la sección y los posibles
socios comunitarios de cada fila.
"""
import re


DIAS_SEMANA = [
    ("Lu", "Lunes"),
    ("Ma", "Martes"),
    ("Mi", "Miércoles"),
    ("Ju", "Jueves"),
    ("Vi", "Viernes"),
    ("Sá", "Sábado"),
]
_CODIGOS_DIAS = [codigo for codigo, _ in DIAS_SEMANA]
_NOMBRE_DIA = dict(DIAS_SEMANA)

_CODIGO_DE = {**{codigo: codigo for codigo in _CODIGOS_DIAS}, **{nombre: codigo for codigo, nombre in DIAS_SEMANA}}

_PATRON_PARTE = re.compile(
    r"^(?P<dia>%(d)s)(?: (?P<hora>\d{2}:\d{2}))?$"
    % {"d": "|".join(sorted(_CODIGO_DE, key=len, reverse=True))}
)


SIN_SOCIO = {"", "-", "—", "por definir", "n/a", "na", "no aplica", "sin socio"}
SEPARADOR_SOCIO = " | "


def texto_horario(horas):
    """
    {'Mi': 10:00, 'Lu': 08:30} -> 'Lunes 08:30, Miércoles 10:00'.
    Cada día lleva su hora: una clase puede ser martes 17:00 y jueves 20:00.
    """
    return ", ".join(
        f"{_NOMBRE_DIA[codigo]} {horas[codigo].strftime('%H:%M')}"
        for codigo in _CODIGOS_DIAS
        if codigo in horas
    )


def leer_horario(texto):
    """
    'Lunes 08:30, Miércoles 10:00' -> {'Lu': '08:30', 'Mi': '10:00'}.
    También lee el formato anterior, una hora para todos los días
    ('Lunes, Miércoles 08:30' o 'Lu, Mi 08:30'). None si tiene otro formato.
    """
    horas = {}
    sin_hora = []
    for parte in (texto or "").strip().split(", "):
        coincidencia = _PATRON_PARTE.match(parte)
        if not coincidencia:
            return None
        sin_hora.append(_CODIGO_DE[coincidencia.group("dia")])
        if coincidencia.group("hora"):
            for codigo in sin_hora:
                horas[codigo] = coincidencia.group("hora")
            sin_hora = []
    if sin_hora or not horas:
        return None
    return horas



CAMPOS_SOCIO = ("nombre", "correo", "rubro", "direccion")


def texto_socios(socios):
    """
    Un socio por línea: 'Nombre | correo | rubro | dirección'. Sin socios
    queda vacío y la pantalla muestra «Por definir».
    """
    lineas = []
    for socio in socios:
        partes = [(socio.get(campo) or "").strip().replace("|", "/") for campo in CAMPOS_SOCIO]
        if any(partes):
            lineas.append(SEPARADOR_SOCIO.join(partes).rstrip(" |"))
    return "\n".join(lineas)


def leer_socios(texto):
    """
    Lee lo que guarda texto_socios. Un texto libre de la planilla antigua
    (sin '|') se toma como el nombre, para no perder el dato.
    """
    socios = []
    for linea in (texto or "").splitlines():
        if linea.strip().lower() in SIN_SOCIO:
            continue

        partes = [parte.strip() for parte in linea.split("|")] + [""] * len(CAMPOS_SOCIO)
        socios.append(dict(zip(CAMPOS_SOCIO, partes)))
    return socios
