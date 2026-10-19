"""
Orden por fecha para los listados de lo que llega o se guarda (postulaciones,
cartas, planificaciones, respuestas, cargas). El listado lee el parámetro GET
"orden" y la plantilla incluye "includes/orden_listado.html".
"""
from django.db.models import F

ORDEN_RECIENTES = "recientes"
ORDEN_ANTIGUOS = "antiguos"
ORDEN_NOMBRE = "nombre"

OPCIONES_ORDEN = [
    (ORDEN_RECIENTES, "Más recientes primero"),
    (ORDEN_ANTIGUOS, "Más antiguos primero"),
]


def orden_pedido(request, permitidos=(ORDEN_RECIENTES, ORDEN_ANTIGUOS), por_defecto=ORDEN_RECIENTES):
    orden = request.GET.get("orden")
    return orden if orden in permitidos else por_defecto


def ordenar_por_fecha(queryset, campo, orden):
    """Las filas sin fecha (por ejemplo, un borrador sin envío) quedan al final."""
    if orden == ORDEN_ANTIGUOS:
        return queryset.order_by(F(campo).asc(nulls_last=True), "pk")
    return queryset.order_by(F(campo).desc(nulls_last=True), "-pk")
