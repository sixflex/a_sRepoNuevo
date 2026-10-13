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
