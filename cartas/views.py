from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academico.models import Seccion
from usuarios.permissions import es_coordinador, es_docente

from .forms import SolicitudCartaForm
from .models import CartaEstudiante, SolicitudCarta
from django.views.decorators.http import require_POST
from .services import generar_pdf_carta

@login_required
def solicitar_carta_docente(request, seccion_id):
    seccion = get_object_or_404(
        Seccion.objects.select_related(
            "campus",
            "campus__sede",
            "asignatura",
            "periodo",
        ),
        id=seccion_id,
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

    if not seccion.docentes.filter(id=docente.id).exists():
        raise PermissionDenied

    if not hasattr(seccion, "ruta_asignada"):
        raise PermissionDenied

    if request.method == "POST":
        form = SolicitudCartaForm(
            request.POST,
            seccion=seccion,
        )

        if form.is_valid():
            solicitud = form.save(commit=False)

            equipo = solicitud.equipo

            if equipo is not None and equipo.seccion_id != seccion.id:
                raise PermissionDenied

            solicitud.seccion = seccion
            solicitud.campus = seccion.campus
            solicitud.sede = seccion.campus.sede
            solicitud.solicitante_usuario = request.user
            solicitud.docente_derivador = docente
            solicitud.solicitante_tipo = "DOCENTE"
            solicitud.solicitante_nombre = (
                f"{docente.nombres} {docente.apellidos}"
            ).strip()
            solicitud.solicitante_correo = (
                docente.correo_institucional
            )
            solicitud.solicitante_entra_id = None
            solicitud.estado = "PENDIENTE"
            solicitud.fecha_solicitud = timezone.now()

            if equipo is not None:
                solicitud.socio = equipo.socio_comunitario

            solicitud.save()
            if equipo is not None:
                integrantes = equipo.integrantes.all().order_by("id")

                for orden, integrante in enumerate(integrantes, start=1):
                    CartaEstudiante.objects.create(
                        solicitud=solicitud,
                        nombre=f"{integrante.nombres} {integrante.apellidos}".strip(),
                        rut=integrante.rut,
                        orden=orden,
                    )

            messages.success(
                request,
                "La solicitud de Carta de Presentación fue enviada correctamente.",
            )

            return redirect(
                "rutas:detalle_ruta_docente",
                seccion_ruta_id=seccion.ruta_asignada.id,
            )
    else:
        form = SolicitudCartaForm(
            seccion=seccion,
        )

    solicitudes = (
        SolicitudCarta.objects
        .filter(
            seccion=seccion,
            solicitante_usuario=request.user,
        )
        .select_related(
            "equipo",
            "socio",
        )
        .order_by("-fecha_solicitud")
    )

    return render(
        request,
        "cartas/solicitar_carta_docente.html",
        {
            "form": form,
            "seccion": seccion,
            "solicitudes": solicitudes,
        },
    )
@login_required
def editar_solicitud_docente(request, solicitud_id):
    solicitud = get_object_or_404(
        SolicitudCarta.objects.select_related(
            "seccion",
            "seccion__campus",
            "seccion__campus__sede",
        ),
        id=solicitud_id,
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

    if solicitud.solicitante_usuario_id != request.user.id:
        raise PermissionDenied

    if solicitud.estado != "OBSERVADA":
        messages.error(
            request,
            "Solo se pueden editar solicitudes observadas.",
        )

        return redirect(
            "cartas:solicitar_carta_docente",
            seccion_id=solicitud.seccion_id,
        )

    seccion = solicitud.seccion

    if request.method == "POST":
        form = SolicitudCartaForm(
            request.POST,
            instance=solicitud,
            seccion=seccion,
        )

        if form.is_valid():
            solicitud = form.save(commit=False)

            if (
                solicitud.equipo is not None
                and solicitud.equipo.seccion_id != seccion.id
            ):
                raise PermissionDenied

            solicitud.campus = seccion.campus
            solicitud.sede = seccion.campus.sede
            solicitud.socio = (
                solicitud.equipo.socio_comunitario
                if solicitud.equipo
                else None
            )
            solicitud.estado = "PENDIENTE"
            solicitud.motivo_observacion = None
            solicitud.fecha_aprobacion = None
            solicitud.fecha_solicitud = timezone.now()

            solicitud.save()

            messages.success(
                request,
                "La solicitud fue corregida y reenviada correctamente.",
            )

            return redirect(
                "cartas:solicitar_carta_docente",
                seccion_id=seccion.id,
            )
    else:
        form = SolicitudCartaForm(
            instance=solicitud,
            seccion=seccion,
        )

    return render(
        request,
        "cartas/editar_solicitud_docente.html",
        {
            "form": form,
            "solicitud": solicitud,
            "seccion": seccion,
        },
    )
@login_required
def listar_solicitudes_coordinacion(request):
    if not es_coordinador(request.user):
        raise PermissionDenied

    solicitudes = (
        SolicitudCarta.objects
        .select_related(
            "seccion",
            "seccion__asignatura",
            "campus",
            "sede",
            "docente_derivador",
            "equipo",
            "socio",
        )
        .order_by("-fecha_solicitud")
    )

    return render(
        request,
        "cartas/listar_solicitudes_coordinacion.html",
        {
            "solicitudes": solicitudes,
        },
    )


@login_required
def detalle_solicitud_coordinacion(request, solicitud_id):
    if not es_coordinador(request.user):
        raise PermissionDenied

    solicitud = get_object_or_404(
        SolicitudCarta.objects.select_related(
            "seccion",
            "seccion__asignatura",
            "campus",
            "sede",
            "docente_derivador",
            "equipo",
            "socio",
        ).prefetch_related(
            "estudiantes",
            "documentos",
        ),
        id=solicitud_id,
    )

    return render(
        request,
        "cartas/detalle_solicitud_coordinacion.html",
        {
            "solicitud": solicitud,
        },
    )


@login_required
@require_POST
def aprobar_solicitud(request, solicitud_id):
    if not es_coordinador(request.user):
        raise PermissionDenied

    solicitud = get_object_or_404(
        SolicitudCarta,
        id=solicitud_id,
    )

    if solicitud.estado != "PENDIENTE":
        messages.error(
            request,
            "Solo se pueden aprobar solicitudes pendientes.",
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    solicitud.estado = "APROBADA"
    solicitud.fecha_aprobacion = timezone.now()
    solicitud.motivo_observacion = None

    solicitud.save(
        update_fields=[
            "estado",
            "fecha_aprobacion",
            "motivo_observacion",
        ]
    )

    messages.success(
        request,
        "La solicitud fue aprobada correctamente.",
    )

    return redirect(
        "cartas:detalle_solicitud_coordinacion",
        solicitud_id=solicitud.id,
    )


@login_required
@require_POST
def observar_solicitud(request, solicitud_id):
    if not es_coordinador(request.user):
        raise PermissionDenied

    solicitud = get_object_or_404(
        SolicitudCarta,
        id=solicitud_id,
    )

    if solicitud.estado != "PENDIENTE":
        messages.error(
            request,
            "Solo se pueden observar solicitudes pendientes.",
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    motivo = request.POST.get(
        "motivo_observacion",
        "",
    ).strip()

    if not motivo:
        messages.error(
            request,
            "Debes indicar el motivo de la observación.",
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    solicitud.estado = "OBSERVADA"
    solicitud.motivo_observacion = motivo
    solicitud.fecha_aprobacion = None

    solicitud.save(
        update_fields=[
            "estado",
            "motivo_observacion",
            "fecha_aprobacion",
        ]
    )

    messages.success(
        request,
        "La solicitud fue observada correctamente.",
    )

    return redirect(
        "cartas:detalle_solicitud_coordinacion",
        solicitud_id=solicitud.id,
    )
@login_required
@require_POST
def generar_carta_pdf(request, solicitud_id):
    if not es_coordinador(request.user):
        raise PermissionDenied

    solicitud = get_object_or_404(
        SolicitudCarta.objects.select_related(
            "seccion",
            "seccion__asignatura",
            "docente_derivador",
        ).prefetch_related(
            "estudiantes",
            "documentos",
        ),
        id=solicitud_id,
    )

    if solicitud.estado != "APROBADA":
        messages.error(
            request,
            "Solo se puede generar la carta de una solicitud aprobada.",
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    try:
        documento = generar_pdf_carta(
            solicitud,
            request.user,
        )
    except ValueError as error:
        messages.error(
            request,
            str(error),
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    messages.success(
        request,
        f"Carta PDF versión {documento.numero_version} generada correctamente.",
    )

    return redirect(
        "cartas:detalle_solicitud_coordinacion",
        solicitud_id=solicitud.id,
    )