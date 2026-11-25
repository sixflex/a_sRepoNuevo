"""
"Volver" que recuerda de dónde vino el usuario.

Una página que se abre desde dos lugares (por ejemplo, Solicitar carta desde
la Ruta o desde la sección) recibe ?volver=<ruta>. Ese origen se guarda en la
sesión para esa página, así sigue valiendo después de usar sus filtros o de
enviar un formulario. Si el usuario vuelve a entrar desde otra página sin
?volver, se olvida y se usa el destino por defecto de la plantilla.
"""

from urllib.parse import urlparse

from django.urls import Resolver404, resolve
from django.utils.http import url_has_allowed_host_and_scheme

CLAVE = "volver:{}"


TEXTOS = {
    "rutas:detalle_ruta_docente": "Volver a la Ruta",
    "core:detalle_seccion": "Volver a la sección",
    "core:docente": "Volver a mis secciones",
    "proyectos:gestionar_equipos_seccion": "Volver a los equipos",
    "proyectos:gestionar_equipo": "Volver al equipo",
    "proyectos:gestionar_registro_equipos": "Volver al registro de equipos",
    "cartas:solicitar_carta_docente": "Volver a solicitar carta",
    "cartas:listar_cartas_seccion_docente": "Volver a las cartas",
    "socios:catalogo_docente": "Volver a los socios",
}


def _valida(request, destino):
    return bool(destino) and destino.startswith("/") and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    )


def destino_volver(request):
    """La página de origen de esta página, o None si no se sabe."""
    if request is None:
        return None
    sesion = getattr(request, "session", None)
    clave = CLAVE.format(request.path)
    destino = request.GET.get("volver", "")
    if _valida(request, destino):
        if sesion is not None:
            sesion[clave] = destino
        return destino
    if sesion is None:
        return None

    referer = urlparse(request.META.get("HTTP_REFERER", ""))
    if referer.path and referer.netloc == request.get_host() and referer.path != request.path:

        sesion.pop(clave, None)
        return None
    return sesion.get(clave)


def texto_volver(destino, defecto="Volver"):
    try:
        coincidencia = resolve(urlparse(destino).path)
    except Resolver404:
        return defecto
    return TEXTOS.get(coincidencia.view_name, defecto)


def con_volver(url, request):
    """url con ?volver=<página actual> (o &volver= si ya tiene parámetros)."""
    from urllib.parse import quote

    separador = "&" if "?" in url else "?"
    return f"{url}{separador}volver={quote(request.get_full_path(), safe='')}"
