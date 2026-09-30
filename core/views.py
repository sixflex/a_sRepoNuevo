from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_required, docente_required

from academico.models import (
    Asignatura,
    Docente,
    PeriodoAcademico,
    Seccion,
)


def inicio(request):
    if request.user.is_authenticated:
        if es_coordinador(request.user):
            return redirect("core:coordinacion")
        if es_docente(request.user):
            return redirect("core:docente")

    return render(request, "core/inicio.html")


@coordinador_required
def panel_coordinacion(request):
    total_secciones = Seccion.objects.filter(
        estado__iexact="Activo"
    ).count()

    total_docentes = Docente.objects.filter(
        activo=True
    ).count()

    total_asignaturas = Asignatura.objects.filter(
        activo=True
    ).count()

    total_periodos = PeriodoAcademico.objects.filter(
        estado__iexact="Activo"
    ).count()

    periodo_actual = (
        PeriodoAcademico.objects
        .filter(estado__iexact="Activo")
        .order_by("-anio", "-id")
        .first()
    )

    return render(
        request,
        "core/coordinacion.html",
        {
            "total_secciones": total_secciones,
            "total_docentes": total_docentes,
            "total_asignaturas": total_asignaturas,
            "total_periodos": total_periodos,
            "periodo_actual": periodo_actual,
        },
    )


@coordinador_required
def planificacion_coordinacion(request):
    from planificacion.models import Planificacion

    planificaciones = (
        Planificacion.objects
        .select_related(
            "enlace",
            "enlace__campus",
            "enlace__campus__sede",
            "enlace__periodo",
            "enlace__unidad_academica",
            "enlace__unidad_academica__facultad",
            "enlace__unidad_academica__carrera",
        )
        .prefetch_related(
            "filas__docentes",
            "filas__errores",
        )
        .order_by("-fecha_envio_final", "-id")
    )

    return render(
        request,
        "core/planificacion_coordinacion.html",
        {
            "planificaciones": planificaciones,
        },
    )


@docente_required
def panel_docente(request):
    secciones = (
        Seccion.objects
        .filter(docentes__usuario=request.user)
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .distinct()
    )

    return render(
        request,
        "core/docente.html",
        {
            "secciones": secciones,
        },
    )


@login_required
def detalle_seccion(request, seccion_id):
    seccion = get_object_or_404(
        Seccion.objects
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .prefetch_related("docentes"),
        id=seccion_id,
    )

    if es_coordinador(request.user):
        pass

    elif es_docente(request.user):
        pertenece_al_docente = seccion.docentes.filter(
            usuario=request.user
        ).exists()

        if not pertenece_al_docente:
            raise PermissionDenied

    else:
        raise PermissionDenied

    return render(
        request,
        "core/detalle_seccion.html",
        {
            "seccion": seccion,
        },
    )


@coordinador_required
def detalle_planificacion_coordinacion(
    request,
    planificacion_id,
):
    from planificacion.models import Planificacion

    planificacion = get_object_or_404(
        Planificacion.objects
        .select_related(
            "enlace",
            "enlace__campus",
            "enlace__campus__sede",
            "enlace__periodo",
            "enlace__unidad_academica",
            "enlace__unidad_academica__facultad",
            "enlace__unidad_academica__carrera",
        )
        .prefetch_related(
            "filas__docentes",
            "filas__errores",
        ),
        id=planificacion_id,
    )

    filas = (
        planificacion.filas.all()
        .prefetch_related("docentes", "errores")
        .order_by("numero_fila", "id")
    )

    return render(
        request,
        "core/detalle_planificacion_coordinacion.html",
        {
            "planificacion": planificacion,
            "filas": filas,
        },
    )