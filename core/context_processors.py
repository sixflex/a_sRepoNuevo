"""
Ítem activo del menú lateral (templates/includes/sidebar.html).

Se calcula aquí, a partir de la URL resuelta, para que el ítem del menú
quede marcado en todas las páginas de su sección (listados, detalles y
formularios) sin repetir listas de nombres de URL en la plantilla.
"""


MENU_CORE = {
    "coordinacion": "inicio",
    "inicio_docente": "inicio",
    "docente": "secciones",
    "detalle_seccion": "secciones",
    "planificacion_coordinacion": "planificaciones",
    "detalle_planificacion_coordinacion": "planificaciones",
}


MENU_POR_APP = {
    "rutas": "rutas",
    "cartas": "cartas",
    "encuestas": "encuestas",
    "historicos": "historicos",
    "archivos": "repositorio",
    "publico": "repositorio",
    "reportes": "reportes",
    "comunicaciones": "configuracion",
}


def _menu_activo(match):
    namespace = match.namespace
    nombre = match.url_name or ""

    if namespace == "core":
        return MENU_CORE.get(nombre, "")


    if namespace == "cartas" and "plantilla_carta" in nombre:
        return "configuracion"

    if namespace in MENU_POR_APP:
        return MENU_POR_APP[namespace]

    if namespace == "socios":
        if nombre in ("lista_postulaciones", "detalle_postulacion", "revisar_postulacion", "revisar_socio_propuesto"):
            return "postulaciones"
        return "socios"

    if namespace == "proyectos" and nombre == "gestionar_enlaces":
        return "enlaces"

    if namespace == "proyectos" and nombre == "catalogo":
        return "proyectos"


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
