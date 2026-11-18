"""
Catálogo de comunas de Chile (RNF-DAT-01: los filtros no dependen de
interpretar texto libre).

La lista oficial (346 comunas, con su región y un punto aproximado para el
mapa) está en socios/datos/comunas_chile.json; se carga en la tabla Comuna
con `python manage.py cargar_catalogos_socios` (datos de los paquetes npm
@clregions/data y comunas-chile-mjt, licencia MIT). Aquí está lo que usan los
formularios, el registro de equipos y la carga histórica para que
"la florida", "LA FLORIDA" o "La  Florida" sean siempre la misma comuna.
"""

import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

ARCHIVO_COMUNAS = Path(__file__).resolve().parent / "datos" / "comunas_chile.json"


def clave(texto):
    """Nombre comparable: sin tildes, mayúsculas, signos ni espacios dobles."""
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", texto.lower()).split())


def comunas_oficiales():
    with open(ARCHIVO_COMUNAS, encoding="utf-8") as archivo:
        return json.load(archivo)


def cargar_catalogo():
    """
    Deja en la tabla Comuna las 346 comunas oficiales. Una comuna que ya
    existe (aunque esté escrita con otras mayúsculas o sin tildes) se
    reutiliza: solo se completa su región y su ubicación si faltaban.
    Devuelve (creadas, completadas).
    """
    from .models import Comuna

    existentes = {clave(c.nombre): c for c in Comuna.objects.all()}
    creadas = completadas = 0
    for fila in comunas_oficiales():
        lat = Decimal(str(fila["lat"])) if fila["lat"] is not None else None
        lon = Decimal(str(fila["lon"])) if fila["lon"] is not None else None
        comuna = existentes.get(clave(fila["nombre"]))
        if comuna is None:
            Comuna.objects.create(
                nombre=fila["nombre"], region=fila["region"],
                lat_centro=lat, lon_centro=lon, activo=True,
            )
            creadas += 1
            continue
        cambios = []
        if not comuna.region:
            comuna.region = fila["region"]
            cambios.append("region")
        if comuna.lat_centro is None and lat is not None:
            comuna.lat_centro, comuna.lon_centro = lat, lon
            cambios += ["lat_centro", "lon_centro"]
        if cambios:
            comuna.save(update_fields=cambios)
            completadas += 1
    return creadas, completadas


def buscar_comuna(texto):
    """La comuna del catálogo que corresponde al texto, o None."""
    from .models import Comuna

    buscada = clave(texto)
    if not buscada:
        return None
    for comuna in Comuna.objects.filter(activo=True):
        if clave(comuna.nombre) == buscada:
            return comuna
    return None


def nombres_comunas():
    """Nombres para la lista desplegable, en orden alfabético."""
    from .models import Comuna

    return sorted(
        Comuna.objects.filter(activo=True).values_list("nombre", flat=True).distinct(),
        key=clave,
    )
