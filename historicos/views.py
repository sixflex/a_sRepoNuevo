from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from academico.models import Campus
from core.ordenamiento import OPCIONES_ORDEN, orden_pedido, ordenar_por_fecha
from usuarios.decorators import coordinador_required

from . import services
from .models import CargaHistorica

# Filas aceptadas que se muestran de ejemplo en la vista previa.
MUESTRA_ACEPTADAS = 5


@coordinador_required
def cargas(request):
    """Importar históricos (RF-MIG-01): arrastrar la exportación y ver las cargas anteriores."""
    if request.method == "POST":
        archivo = request.FILES.get("archivo")
        if archivo is None:
            messages.error(request, "Elige o arrastra el archivo exportado.")
        else:
            try:
                carga = services.analizar_archivo(
                    archivo=archivo, tipo=request.POST.get("tipo", ""), usuario=request.user,
                )
            except ValidationError as error:
                messages.error(request, error.messages[0])
            else:
                return redirect("historicos:detalle", carga_id=carga.id)

    orden = orden_pedido(request)
    lista = ordenar_por_fecha(
        CargaHistorica.objects.select_related("archivo", "responsable_usuario"), "fecha_carga", orden,
    )[:50]
    tipos = dict(services.tipos_origen())
    for carga in lista:
        carga.nombre_tipo = tipos.get(carga.tipo_origen, carga.tipo_origen)
        carga.nombre_estado = services.ESTADOS_CARGA.get(carga.estado, carga.estado)
    return render(request, "historicos/cargas.html", {
        "tipos": services.tipos_origen(),
        "tipo_elegido": request.POST.get("tipo", ""),
        "cargas": lista,
        "orden": orden,
        "opciones_orden": OPCIONES_ORDEN,
    })


@coordinador_required
def detalle(request, carga_id):
    """Vista previa antes de confirmar (RF-MIG-01 CA1) o resultado de una carga ya hecha."""
    carga = get_object_or_404(
        CargaHistorica.objects.select_related("archivo", "responsable_usuario"), pk=carga_id,
    )
    filas = list(carga.filas.prefetch_related("errores").order_by("numero_fila"))
    con_problemas = [fila for fila in filas if fila.estado != services.FILA_ACEPTADA]
    aceptadas = [fila for fila in filas if fila.estado == services.FILA_ACEPTADA]
    mapeos = list(carga.mapeos.order_by("id"))
    reconocidas = {mapeo.columna_origen for mapeo in mapeos}
    columnas = list(filas[0].datos_raw_json) if filas else []

    campus = Campus.objects.select_related("sede").order_by("sede__nombre", "nombre")
    # Carga inicial del piloto: Sede Santiago, Campus Providencia (RN-01).
    campus_sugerido = campus.filter(nombre__icontains="providencia").first() or campus.first()

    return render(request, "historicos/detalle.html", {
        "carga": carga,
        "nombre_tipo": services.nombre_tipo(carga.tipo_origen),
        "nombre_estado": services.ESTADOS_CARGA.get(carga.estado, carga.estado),
        "es_previa": carga.estado == services.ESTADO_PREVIA,
        "es_confirmada": carga.estado == services.ESTADO_CONFIRMADA,
        "es_registro_socios": carga.tipo_origen == services.TIPO_REGISTRO_SOCIOS,
        "mapeos": mapeos,
        "no_reconocidas": [columna for columna in columnas if columna not in reconocidas],
        "con_problemas": con_problemas,
        "muestra_aceptadas": aceptadas[:MUESTRA_ACEPTADAS],
        "importables": carga.aceptadas + carga.observadas,
        "campus": campus,
        "campus_sugerido": campus_sugerido,
        "resultado": {
            "respuestas": sum(1 for fila in filas if fila.respuesta_resultante_id),
            "socios": len({fila.socio_resultante_id for fila in filas if fila.socio_resultante_id}),
        },
    })


@coordinador_required
@require_POST
def confirmar(request, carga_id):
    carga = get_object_or_404(CargaHistorica, pk=carga_id)
    campus = Campus.objects.select_related("sede").filter(pk=request.POST.get("campus") or None).first()
    try:
        creados = services.confirmar_carga(request, carga, campus)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        if "respuestas" in creados:
            resumen = f"{creados['respuestas']} respuestas importadas."
        else:
            resumen = (
                f"{creados['participaciones']} participaciones importadas "
                f"({creados['socios_nuevos']} socios nuevos)."
            )
        messages.success(request, f"Carga confirmada: {resumen}")
    return redirect("historicos:detalle", carga_id=carga.id)


@coordinador_required
@require_POST
def cancelar(request, carga_id):
    carga = get_object_or_404(CargaHistorica, pk=carga_id)
    try:
        services.cancelar_carga(carga)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.info(request, "Carga cancelada: no se importó ninguna fila.")
    return redirect("historicos:cargas")
