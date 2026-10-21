"""
Ítem activo del menú lateral (templates/includes/sidebar.html).

Se calcula aquí, a partir de la URL resuelta, para que el ítem del menú
quede marcado en todas las páginas de su sección (listados, detalles y
formularios) sin repetir listas de nombres de URL en la plantilla.
"""

# Páginas del espacio de nombres "core" que pertenecen a un ítem del menú.
MENU_CORE = {
    "coordinacion": "inicio",
    "inicio_docente": "inicio",
    "docente": "secciones",
    "detalle_seccion": "secciones",
    "planificacion_coordinacion": "planificaciones",
    "detalle_planificacion_coordinacion": "planificaciones",
}

# Apps cuyo espacio de nombres corresponde completo a un ítem del menú.
MENU_POR_APP = {
    "rutas": "rutas",
    "cartas": "cartas",
    "encuestas": "encuestas",
    "historicos": "historicos",
}


def _menu_activo(match):
    namespace = match.namespace
    nombre = match.url_name or ""

    if namespace == "core":
        return MENU_CORE.get(nombre, "")

    if namespace in MENU_POR_APP:
        return MENU_POR_APP[namespace]

    if namespace == "socios":
        if nombre in ("lista_postulaciones", "detalle_postulacion", "revisar_postulacion", "revisar_socio_propuesto"):
            return "postulaciones"
        return "socios"

    if namespace == "proyectos" and nombre == "gestionar_enlaces":
        return "enlaces"

    # Las URLs de academico no tienen espacio de nombres.
    if match.route.startswith("academico/"):
        if nombre.startswith("seccion_"):
            return "secciones"
        return "academico"

    return ""


def menu_lateral(request):
    match = getattr(request, "resolver_match", None)

    if match is None:
        return {}

    return {"menu_activo": _menu_activo(match)}
