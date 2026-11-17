import re

from django import template


register = template.Library()


@register.filter
def estado_legible(valor):
    """
    Muestra un estado guardado como constante en forma legible:
    "EN_PROGRESO" -> "En progreso", "TRABAJO_TERMINADO" -> "Trabajo terminado".

    Si el campo tiene choices, preferir get_<campo>_display; este filtro es
    para los estados que se guardan como texto sin choices.
    """
    if not valor:
        return ""

    return str(valor).replace("_", " ").strip().capitalize()


@register.filter
def nombre_visible(usuario):
    """
    Nombre que se muestra en la barra superior en vez del correo.

    Usa el nombre y apellido guardados; si no hay, lo arma desde el correo
    institucional (nombre.apellido2@cloud.uautonoma.cl -> "Nombre Apellido").
    """
    if not usuario:
        return ""
    completo = (usuario.get_full_name() or "").strip()
    if completo:
        return completo
    correo = next(
        (c for c in (getattr(usuario, "correo_institucional", ""), usuario.email, usuario.username) if c and "@" in c),
        "",
    )
    if not correo:
        return usuario.username
    partes = [re.sub(r"\d+", "", parte) for parte in re.split(r"[._\-]+", correo.split("@", 1)[0])]
    return " ".join(parte.capitalize() for parte in partes if parte) or usuario.username


@register.inclusion_tag("includes/volver.html", takes_context=True)
def volver(context, url_defecto, texto="Volver"):
    """
    Enlace "Volver" único del portal: arriba a la izquierda, sobre el título.

    Si la página se abrió desde otra con ?volver=<ruta> (por ejemplo, "Ver
    socio" desde el catálogo de Proyectos), vuelve a esa página; si no, a
    url_defecto. Solo acepta rutas del mismo sitio.
    """
    from django.utils.http import url_has_allowed_host_and_scheme

    request = context.get("request")
    destino = request.GET.get("volver", "") if request else ""
    if destino.startswith("/") and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return {"url": destino, "texto": "Volver"}
    return {"url": url_defecto, "texto": texto}
