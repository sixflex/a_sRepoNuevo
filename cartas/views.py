from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from academico.models import Docente, Seccion
from core.ordenamiento import OPCIONES_ORDEN, orden_pedido, ordenar_por_fecha
from usuarios.permissions import es_coordinador, es_docente

from .models import (
    CartaEstudiante,
    EnlaceSolicitudCarta,
    SolicitudCarta,
    CartaDocumento,
)
from .services import (
    aprobar_y_enviar_carta,
    corregir_solicitud_coordinacion,
    enviar_carta_docente,
    generar_borrador_carta,
    ultimo_envio,
)
from archivos.services import abrir_archivo
from django.http import FileResponse, Http404

from .forms import SolicitudCartaForm
from .models import CartaEstudiante, SolicitudCarta
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login
from django.views.decorators.http import require_POST

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
                solicitud.socio = equipo.socio_vigente

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
                solicitud.equipo.socio_vigente
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
    )
    prioridad_pendientes = request.GET.get("prioridad") == "pendientes"

    if prioridad_pendientes:
        solicitudes = solicitudes.order_by(
            "fecha_solicitud", "id"
        ).filter(estado="PENDIENTE")
    else:
        orden = orden_pedido(request)
        solicitudes = ordenar_por_fecha(
            solicitudes, "fecha_solicitud", orden
        )
    if prioridad_pendientes:
        orden = "asc"

    return render(
        request,
        "cartas/listar_solicitudes_coordinacion.html",
        {
            "solicitudes": solicitudes,
            "orden": orden,
            "opciones_orden": OPCIONES_ORDEN,
            "prioridad_pendientes": prioridad_pendientes,
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

    documentos = [
        (documento, ultimo_envio(documento))
        for documento in solicitud.documentos.all()
    ]

    return render(
        request,
        "cartas/detalle_solicitud_coordinacion.html",
        {
            "solicitud": solicitud,
            "documentos": documentos,
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

    if solicitud.estado not in {"PENDIENTE", "BORRADOR"}:
        messages.error(
            request,
            "Solo se pueden aprobar solicitudes pendientes o en borrador.",
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    try:
        solicitud, envios = aprobar_y_enviar_carta(
            solicitud.id,
            request.user,
        )
    except ValueError as error:
        messages.error(
            request,
            f"No se pudo aprobar la solicitud: {error}",
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    if all(envio.resultado == "OK" for envio in envios):
        messages.success(
            request,
            "La solicitud fue aprobada y la carta se envió a "
            f"{solicitud.docente_derivador.correo_institucional}.",
        )
    else:
        messages.warning(
            request,
            "La solicitud fue aprobada, pero la carta no se pudo enviar. "
            "Quedó pendiente de envío y puedes reintentarlo desde aquí.",
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
def vista_previa_carta_coordinacion(request, solicitud_id):
    """SP6-T04 (RF-CAR-04): vista previa de la carta, marcada como borrador."""
    if not es_coordinador(request.user):
        raise PermissionDenied

    solicitud = get_object_or_404(
        SolicitudCarta.objects.select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__campus",
            "seccion__campus__sede",
            "campus",
            "sede",
            "docente_derivador",
            "equipo",
            "socio",
        ).prefetch_related("estudiantes"),
        id=solicitud_id,
    )

    try:
        solicitud, documento = generar_borrador_carta(
            solicitud.id,
            request.user,
            request=request,
        )
    except ValueError as error:
        messages.error(
            request,
            f"No se pudo generar la vista previa: {error}",
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    form = SolicitudCartaForm(
        instance=solicitud,
        seccion=solicitud.seccion,
    )

    return render(
        request,
        "cartas/vista_previa_carta.html",
        {
            "solicitud": solicitud,
            "documento": documento,
            "form": form,
            "es_borrador": solicitud.estado == "BORRADOR",
        },
    )


@login_required
@require_POST
def corregir_carta_coordinacion(request, solicitud_id):
    """SP6-T04 (RF-CAR-04): Coordinación corrige datos y regenera el borrador."""
    if not es_coordinador(request.user):
        raise PermissionDenied

    solicitud = get_object_or_404(
        SolicitudCarta,
        id=solicitud_id,
    )

    if solicitud.estado not in {"PENDIENTE", "BORRADOR"}:
        messages.error(
            request,
            "Solo se pueden corregir solicitudes pendientes o en borrador.",
        )

        return redirect(
            "cartas:detalle_solicitud_coordinacion",
            solicitud_id=solicitud.id,
        )

    form = SolicitudCartaForm(
        request.POST,
        instance=solicitud,
        seccion=solicitud.seccion,
    )

    if not form.is_valid():
        messages.error(
            request,
            "Revisa los datos ingresados antes de regenerar la carta.",
        )

        return render(
            request,
            "cartas/vista_previa_carta.html",
            {
                "solicitud": solicitud,
                "documento": None,
                "form": form,
                "es_borrador": solicitud.estado == "BORRADOR",
            },
        )

    datos = {
        campo: form.cleaned_data.get(campo)
        for campo in (
            "institucion_receptora",
            "persona_receptora",
            "cargo_receptor",
            "consideraciones",
        )
    }

    solicitud, documento = corregir_solicitud_coordinacion(
        solicitud.id,
        datos,
        request.user,
        request=request,
    )

    messages.success(
        request,
        "Las correcciones fueron registradas y la carta se regeneró "
        "como borrador.",
    )

    return redirect(
        "cartas:vista_previa_carta_coordinacion",
        solicitud_id=solicitud.id,
    )


@login_required
@require_POST
def reintentar_envio_carta(request, documento_id):
    if not es_coordinador(request.user):
        raise PermissionDenied

    documento = get_object_or_404(
        CartaDocumento.objects.select_related(
            "solicitud",
            "solicitud__seccion__asignatura",
            "solicitud__docente_derivador",
        ),
        id=documento_id,
    )

    envio = enviar_carta_docente(documento)

    if envio.resultado == "OK":
        messages.success(
            request,
            f"La carta se envió a {envio.destinatario}.",
        )
    else:
        messages.error(
            request,
            f"No se pudo enviar la carta: {envio.detalle_error}",
        )

    return redirect(
        "cartas:detalle_solicitud_coordinacion",
        solicitud_id=documento.solicitud_id,
    )


@login_required
def descargar_carta_pdf(request, documento_id):
    documento = get_object_or_404(
        CartaDocumento.objects.select_related("archivo", "solicitud"),
        id=documento_id,
    )

    docente = getattr(request.user, "perfil_docente", None)
    es_su_docente = (
        es_docente(request.user)
        and docente is not None
        and docente.id == documento.solicitud.docente_derivador_id
    )

    if not es_coordinador(request.user) and not es_su_docente:
        raise PermissionDenied

    try:
        contenido = abrir_archivo(documento.archivo)
    except FileNotFoundError as exc:
        raise Http404("El archivo PDF no está disponible.") from exc

    return FileResponse(
        contenido,
        content_type="application/pdf",
        filename=documento.archivo.nombre_original,
    )


def solicitar_carta_estudiante(request, token):
    """SP6-T08: el estudiante informante pide la carta desde un enlace.

    Depende del login simulado (SP5-T02): si no está autenticado se le
    redirige al login institucional. La solicitud queda asociada a la
    sección del enlace y al Docente que lo generó, en estado Pendiente.
    """
    enlace = get_object_or_404(
        EnlaceSolicitudCarta.objects.select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
            "seccion__campus",
            "seccion__campus__sede",
            "creado_por_docente",
        ),
        token=token,
    )

    ahora = timezone.now()

    if not enlace.activo:
        return render(
            request,
            "cartas/solicitud_carta_no_disponible.html",
            {
                "motivo": "El enlace para solicitar la carta se encuentra cerrado.",
            },
            status=403,
        )

    if enlace.fecha_expiracion and enlace.fecha_expiracion <= ahora:
        return render(
            request,
            "cartas/solicitud_carta_no_disponible.html",
            {
                "motivo": "El enlace para solicitar la carta ha expirado.",
            },
            status=403,
        )

    if not request.user.is_authenticated:
        return redirect_to_login(
            request.get_full_path(),
            login_url=reverse("usuarios:login"),
        )

    es_estudiante = request.user.groups.filter(
        name="Estudiante"
    ).exists()

    if not es_estudiante:
        return render(
            request,
            "cartas/solicitud_carta_no_disponible.html",
            {
                "motivo": (
                    "Este formulario solo puede ser utilizado "
                    "por estudiantes autenticados."
                ),
            },
            status=403,
        )

    seccion = enlace.seccion

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
            solicitud.docente_derivador = enlace.creado_por_docente
            solicitud.solicitante_tipo = "ESTUDIANTE"
            solicitud.solicitante_nombre = (
                f"{request.user.first_name} {request.user.last_name}"
            ).strip() or request.user.username
            solicitud.solicitante_correo = (
                request.user.correo_institucional
                or request.user.email
                or request.user.username
            )
            solicitud.solicitante_entra_id = request.user.entra_oid or None
            solicitud.estado = "PENDIENTE"
            solicitud.fecha_solicitud = timezone.now()

            if equipo is not None:
                solicitud.socio = equipo.socio_vigente

            solicitud.save()

            messages.success(
                request,
                "Tu solicitud de Carta de Presentación fue enviada "
                "correctamente.",
            )

            return redirect(
                "cartas:solicitar_carta_estudiante",
                token=enlace.token,
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
        .order_by("-fecha_solicitud")
    )

    return render(
        request,
        "cartas/solicitar_carta_estudiante.html",
        {
            "form": form,
            "enlace": enlace,
            "seccion": seccion,
            "solicitudes": solicitudes,
        },
    )
