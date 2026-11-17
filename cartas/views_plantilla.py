"""
Configuración → Carta oficial: el Coordinador sube su Word oficial (con su
firma, el logo y su tarjeta) y el portal arma con él cada carta aprobada.
"""

from datetime import date

from django.contrib import messages
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from archivos.services import abrir_archivo, guardar_archivo
from auditoria.services import registrar_auditoria
from usuarios.decorators import coordinador_required

from . import plantilla_oficial
from .forms import PlantillaCartaForm
from .models import PlantillaCarta


def _auditar(request, plantilla, accion, anterior=None):
    registrar_auditoria(
        request=request,
        entidad="PlantillaCarta",
        entidad_id=plantilla.pk if plantilla else "-",
        accion=accion,
        valores_anteriores={"plantilla_activa": anterior.pk} if anterior else None,
        valores_nuevos={
            "plantilla_activa": plantilla.pk if plantilla else None,
            "archivo": plantilla.archivo.nombre_original if plantilla else None,
            "hash": plantilla.archivo.hash_sha256 if plantilla else None,
        },
    )


def _activar(plantilla):
    PlantillaCarta.objects.filter(activa=True).exclude(pk=plantilla.pk).update(activa=False)
    plantilla.activa = True
    plantilla.save(update_fields=["activa"])


def _origen_sin_plantilla():
    """Qué se usa cuando no hay carta oficial subida (solo para mostrarlo)."""
    recursos = plantilla_oficial.recursos_carta()
    if recursos["firma"]:
        return "la planilla o la firma de prueba configurada en el servidor"
    return "el texto «Coordinación A+S» sin firma (no hay firma configurada)"


@coordinador_required
def plantilla_carta(request):
    form = PlantillaCartaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        anterior = plantilla_oficial.plantilla_activa()
        with transaction.atomic():
            archivo = guardar_archivo(form.cleaned_data["archivo"], autor=request.user)
            plantilla = PlantillaCarta.objects.create(
                archivo=archivo,
                cargada_por_usuario=request.user,
                observacion=form.cleaned_data.get("observacion", ""),
            )
            _activar(plantilla)
            _auditar(request, plantilla, "SUBIR_PLANTILLA_CARTA", anterior)
        avisos = form.avisos()
        messages.success(
            request,
            "Listo: las próximas cartas aprobadas usarán esta carta oficial. Revisa la carta de ejemplo."
            + (f" Ojo: {' '.join(avisos)}" if avisos else ""),
        )
        return redirect("cartas:plantilla_carta")

    plantillas = PlantillaCarta.objects.select_related("archivo", "cargada_por_usuario")
    activa = next((p for p in plantillas if p.activa), None)
    return render(request, "cartas/plantilla_carta.html", {
        "form": form,
        "plantillas": plantillas,
        "activa": activa,
        "origen_sin_plantilla": None if activa else _origen_sin_plantilla(),
    })


@coordinador_required
@require_POST
def activar_plantilla_carta(request, pk):
    plantilla = get_object_or_404(PlantillaCarta, pk=pk)
    anterior = plantilla_oficial.plantilla_activa()
    with transaction.atomic():
        _activar(plantilla)
        _auditar(request, plantilla, "ACTIVAR_PLANTILLA_CARTA", anterior)
    messages.success(request, f"Ahora se usa «{plantilla.archivo.nombre_original}».")
    return redirect("cartas:plantilla_carta")


@coordinador_required
@require_POST
def desactivar_plantilla_carta(request):
    anterior = plantilla_oficial.plantilla_activa()
    if anterior:
        with transaction.atomic():
            PlantillaCarta.objects.filter(activa=True).update(activa=False)
            _auditar(request, None, "DESACTIVAR_PLANTILLA_CARTA", anterior)
    messages.info(request, "Las cartas ya no usan una carta oficial subida al portal.")
    return redirect("cartas:plantilla_carta")


@coordinador_required
def ejemplo_plantilla_carta(request, pk):
    """Carta de ejemplo con datos ficticios, para revisar cómo queda antes de aprobar cartas reales."""
    plantilla = get_object_or_404(PlantillaCarta.objects.select_related("archivo"), pk=pk)
    try:
        recursos = dict(plantilla_oficial.imagenes_de_plantilla(plantilla))
    except Exception as exc:
        raise Http404("No se pudo leer esta carta oficial.") from exc
    if not recursos.get("logo"):
        recursos["logo"] = plantilla_oficial.recursos_carta()["logo"]
    pdf = plantilla_oficial.construir_pdf(
        fecha=date.today(),
        persona_receptora="Nombre de la persona receptora",
        institucion_receptora="Institución de ejemplo",
        asignatura="Asignatura de ejemplo",
        docente="Docente de ejemplo",
        estudiantes=[("Estudiante de ejemplo uno", "11111111-1"), ("Estudiante de ejemplo dos", "22222222-2")],
        borrador=False,
        recursos=recursos,
        proteger=False,
    )
    respuesta = HttpResponse(pdf, content_type="application/pdf")
    respuesta["Content-Disposition"] = 'inline; filename="carta_de_ejemplo.pdf"'
    return respuesta


@coordinador_required
def descargar_plantilla_carta(request, pk):
    plantilla = get_object_or_404(PlantillaCarta.objects.select_related("archivo"), pk=pk)
    try:
        contenido = abrir_archivo(plantilla.archivo)
    except FileNotFoundError as exc:
        raise Http404("El archivo no está disponible.") from exc
    return FileResponse(
        contenido,
        as_attachment=True,
        filename=plantilla.archivo.nombre_original,
        content_type=plantilla.archivo.mime_type,
    )
