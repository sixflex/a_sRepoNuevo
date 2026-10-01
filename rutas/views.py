from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from usuarios.permissions import es_coordinador, es_docente

from .models import SeccionActividad, SeccionRuta


def verificar_acceso_ruta(usuario, seccion_ruta):
    seccion = seccion_ruta.seccion

    if es_coordinador(usuario):
        return

    if es_docente(usuario):
        pertenece_al_docente = seccion.docentes.filter(
            usuario=usuario
        ).exists()

        if pertenece_al_docente:
            return

    raise PermissionDenied


def recalcular_avance(seccion_ruta):
    actividades = SeccionActividad.objects.filter(
        seccion_ruta=seccion_ruta,
        ruta_actividad__es_obligatoria=True,
    )

    total = actividades.count()

    completadas = actividades.filter(
        completada_por_docente__isnull=False
    ).count()

    if total == 0:
        porcentaje = Decimal("0.00")
    else:
        porcentaje = (
            Decimal(completadas)
            / Decimal(total)
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    seccion_ruta.porcentaje_final = porcentaje
    seccion_ruta.save(
        update_fields=["porcentaje_final"]
    )

    return porcentaje


@login_required
def detalle_ruta_docente(request, seccion_ruta_id):
    seccion_ruta = get_object_or_404(
        SeccionRuta.objects
        .select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
            "seccion__campus",
            "seccion__campus__sede",
            "ruta_version",
            "ruta_version__plantilla",
        ),
        id=seccion_ruta_id,
    )

    verificar_acceso_ruta(
        request.user,
        seccion_ruta,
    )

    actividades = (
        seccion_ruta.actividades
        .select_related(
            "ruta_actividad",
            "completada_por_docente",
        )
        .order_by("ruta_actividad__orden")
    )

    etapas = {}

    for actividad in actividades:
        etapa = actividad.ruta_actividad.etapa

        if etapa not in etapas:
            etapas[etapa] = []

        etapas[etapa].append(actividad)

    return render(
        request,
        "rutas/detalle_ruta_docente.html",
        {
            "seccion_ruta": seccion_ruta,
            "seccion": seccion_ruta.seccion,
            "etapas": etapas,
        },
    )


@login_required
@require_POST
def completar_actividad(request, actividad_id):
    actividad = get_object_or_404(
        SeccionActividad.objects.select_related(
            "seccion_ruta",
            "seccion_ruta__seccion",
            "ruta_actividad",
            "completada_por_docente",
        ),
        id=actividad_id,
    )

    seccion_ruta = actividad.seccion_ruta

    verificar_acceso_ruta(
        request.user,
        seccion_ruta,
    )

    if not es_docente(request.user):
        raise PermissionDenied

    docente = getattr(
        request.user,
        "perfil_docente",
        None,
    )

    if docente is None:
        raise PermissionDenied

    if actividad.completada_por_docente_id is None:
        actividad.completada_por_docente = docente
        actividad.estado = "COMPLETADA"
        actividad.fecha_completada = timezone.now()

        actividad.save(
            update_fields=[
                "completada_por_docente",
                "estado",
                "fecha_completada",
            ]
        )

    recalcular_avance(seccion_ruta)

    return redirect(
        "rutas:detalle_ruta_docente",
        seccion_ruta_id=seccion_ruta.id,
    )