from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from proyectos.models import Seccion
from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_required, docente_required
from .models import Docente, PeriodoAcademico
from academico.models import Asignatura, Seccion as SeccionAcademica

@login_required
def inicio(request):

    if es_coordinador(request.user):
        return redirect("core:coordinacion")

    if es_docente(request.user):
        return redirect("core:docente")

    raise PermissionDenied


@coordinador_required
def panel_coordinacion(request):

    total_secciones = SeccionAcademica.objects.filter(estado=True).count()
    total_docentes = Docente.objects.count()

    total_asignaturas = Asignatura.objects.filter(estado=True).count()

    total_periodos = PeriodoAcademico.objects.filter(estado=True).count()

    periodo_actual = (
        PeriodoAcademico.objects
        .filter(estado=True)
        .select_related("anio")
        .order_by("-anio__numero", "-id")
        .first()
    )

    contexto = {
        "total_secciones": total_secciones,
        "total_docentes": total_docentes,
        "total_asignaturas": total_asignaturas,
        "total_periodos": total_periodos,
        "periodo_actual": periodo_actual,
    }

    return render(request,"core/coordinacion.html",contexto,)

@coordinador_required
def planificacion_coordinacion(request):
    return render(
        request,
        "core/planificacion_coordinacion.html",
    )

@docente_required
def panel_docente(request):

    secciones = Seccion.objects.filter(
        docente=request.user
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
        Seccion,
        id=seccion_id,
    )

    if es_coordinador(request.user):
        pass

    elif es_docente(request.user):

        if seccion.docente != request.user:
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