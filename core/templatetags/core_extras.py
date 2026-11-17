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

    Si la página se abrió desde otra con ?volver=<ruta> (por ejemplo, Solicitar
    carta desde la Ruta), vuelve a esa página aunque después se usen filtros o
    se envíe un formulario (core/volver.py); si no, a url_defecto.
    """
    from core.volver import destino_volver, texto_volver

    destino = destino_volver(context.get("request"))
    if destino:
        return {"url": destino, "texto": texto_volver(destino)}
    return {"url": url_defecto, "texto": texto}


@register.simple_tag(takes_context=True)
def url_con_volver(context, url):
    """La url con ?volver=<esta página>, para que su "Volver" regrese aquí."""
    from core.volver import con_volver

    return con_volver(url, context["request"])
