from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from proyectos.models import Seccion
from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_required, docente_required


@login_required
def inicio(request):

    if es_coordinador(request.user):
        return redirect("core:coordinacion")

    if es_docente(request.user):
        return redirect("core:docente")

    raise PermissionDenied


@coordinador_required
def panel_coordinacion(request):
    return render(
        request,
        "core/coordinacion.html",
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