"""
Formatos de texto de la planilla de Dirección que se guardan en campos varchar
del modelo .mmd (sin migraciones): el horario de la sección y los posibles
socios comunitarios de cada fila.
"""
import re

# Código corto del check (Lu) y nombre completo que se guarda y se lee (Lunes).
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
# Se aceptan el nombre completo y el código corto (borradores guardados antes).
_CODIGO_DE = {**{codigo: codigo for codigo in _CODIGOS_DIAS}, **{nombre: codigo for codigo, nombre in DIAS_SEMANA}}

_PATRON_HORARIO = re.compile(
    r"^(?P<dias>(?:%(d)s)(?:, (?:%(d)s))*) (?P<hora>\d{2}:\d{2})$"
    % {"d": "|".join(sorted(_CODIGO_DE, key=len, reverse=True))}
)

# Textos que la planilla original usaba para decir que aún no hay socio.
SIN_SOCIO = {"", "-", "—", "por definir", "n/a", "na", "no aplica", "sin socio"}
SEPARADOR_SOCIO = " | "


def texto_horario(dias, hora):
    """['Lu', 'Mi'] y 08:30 -> 'Lunes, Miércoles 08:30' (días en el orden de la semana)."""
    nombres = [_NOMBRE_DIA[codigo] for codigo in _CODIGOS_DIAS if codigo in set(dias)]
    return f"{', '.join(nombres)} {hora.strftime('%H:%M')}"


def leer_horario(texto):
    """'Lunes, Miércoles 08:30' (o 'Lu, Mi 08:30') -> (['Lu', 'Mi'], '08:30'); None si tiene otro formato."""
    coincidencia = _PATRON_HORARIO.match((texto or "").strip())
    if not coincidencia:
        return None
    return [_CODIGO_DE[dia] for dia in coincidencia.group("dias").split(", ")], coincidencia.group("hora")


def texto_socios(socios):
    """
    Un socio por línea: 'Nombre | correo | rubro'. Sin socios queda vacío y
    la pantalla muestra «Por definir».
    """
    lineas = []
    for socio in socios:
        partes = [(socio.get(campo) or "").strip().replace("|", "/") for campo in ("nombre", "correo", "rubro")]
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
        partes = [parte.strip() for parte in linea.split("|")] + ["", ""]
        socios.append({"nombre": partes[0], "correo": partes[1], "rubro": partes[2]})
    return socios
