from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from archivos.services import guardar_archivo, obtener_storage_privado
from archivos.validators import validar_cantidad_archivos
from auditoria.services import registrar_auditoria
from academico.models import Campus, Sede
from usuarios.permissions import es_coordinador, es_docente
from . import services as servicios
from .models import Evidencia, ExpedienteSeccion, SeccionActividad, SeccionRuta


def verificar_acceso_ruta(user, seccion_ruta):
    if es_coordinador(user):
        return

    if es_docente(user):
        docente = getattr(user, "perfil_docente", None)

        if docente and seccion_ruta.seccion.docentes.filter(
            id=docente.id
        ).exists():
            return

    raise PermissionDenied


def recalcular_avance(seccion_ruta):
    actividades_obligatorias = SeccionActividad.objects.filter(
        seccion_ruta=seccion_ruta,
        ruta_actividad__es_obligatoria=True,
    )

    total = actividades_obligatorias.count()

    if total == 0:
        porcentaje = Decimal("0.00")
    else:
        completadas = actividades_obligatorias.filter(
            completada_por_docente__isnull=False,
        ).count()

        porcentaje = (
            Decimal(completadas)
            / Decimal(total)
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    seccion_ruta.porcentaje_final = porcentaje

    seccion_ruta.save(
        update_fields=[
            "porcentaje_final",
        ]
    )

    return porcentaje


@login_required
def detalle_ruta_docente(request, seccion_ruta_id):
    seccion_ruta = get_object_or_404(
        SeccionRuta.objects.select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
            "seccion__campus",
            "seccion__campus__sede",
            "ruta_version",
            "cerrada_por_docente",
        ),
        id=seccion_ruta_id,
    )

    verificar_acceso_ruta(
        request.user,
        seccion_ruta,
    )

    actividades = (
        SeccionActividad.objects
        .filter(
            seccion_ruta=seccion_ruta,
        )
        .select_related(
            "ruta_actividad",
            "completada_por_docente",
        )
        .prefetch_related(
            "evidencias__archivo",
        )
        .order_by(
            "ruta_actividad__orden",
        )
    )

    etapas = {}

    for actividad in actividades:
        etapa = actividad.ruta_actividad.etapa

        if etapa not in etapas:
            etapas[etapa] = []

        etapas[etapa].append(
            actividad
        )

    obligatorias = actividades.filter(
        ruta_actividad__es_obligatoria=True,
    )

    puede_completar_ruta = (
        obligatorias.exists()
        and not obligatorias.filter(
            completada_por_docente__isnull=True,
        ).exists()
        and seccion_ruta.estado != "COMPLETADA"
    )

    return render(
        request,
        "rutas/detalle_ruta_docente.html",
        {
            "seccion_ruta": seccion_ruta,
            "seccion": seccion_ruta.seccion,
            "etapas": etapas,
            "actividades_con_evidencia": [
                11,
                16,
                20,
                21,
            ],
            "puede_completar_ruta": puede_completar_ruta,
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

    if seccion_ruta.estado == "COMPLETADA":
        messages.error(
            request,
            "La Ruta ya está completada y no puede modificarse.",
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    estado_anterior = actividad.estado

    if actividad.completada_por_docente_id is None:
        actividad.completada_por_docente = docente
        actividad.estado = "COMPLETADA"
        actividad.fecha_completada = timezone.now()
    else:
        actividad.completada_por_docente = None
        actividad.estado = "PENDIENTE"
        actividad.fecha_completada = None

        if actividad.observacion == servicios.OBSERVACION_SIN_CIERRE:
            actividad.observacion = None

    actividad.save(
        update_fields=[
            "completada_por_docente",
            "estado",
            "fecha_completada",
            "observacion",
        ]
    )

    recalcular_avance(
        seccion_ruta
    )

    registrar_auditoria(
        request=request,
        entidad="SeccionActividad",
        entidad_id=actividad.pk,
        accion="MARCAR_ACTIVIDAD" if actividad.estado == "COMPLETADA" else "DESMARCAR_ACTIVIDAD",
        valores_anteriores={"estado": estado_anterior},
        valores_nuevos={
            "estado": actividad.estado,
            "fecha_completada": str(actividad.fecha_completada) if actividad.fecha_completada else None,
        },
    )

    return redirect(
        "rutas:detalle_ruta_docente",
        seccion_ruta_id=seccion_ruta.id,
    )


@login_required
@require_POST
def completar_ruta(request, seccion_ruta_id):
    seccion_ruta = get_object_or_404(
        SeccionRuta.objects.select_related(
            "seccion",
            "cerrada_por_docente",
        ),
        id=seccion_ruta_id,
    )

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

    if seccion_ruta.estado == "COMPLETADA":
        messages.info(
            request,
            "La Ruta ya se encuentra completada.",
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    obligatorias = SeccionActividad.objects.filter(
        seccion_ruta=seccion_ruta,
        ruta_actividad__es_obligatoria=True,
    )

    total_obligatorias = obligatorias.count()

    completadas = obligatorias.filter(
        completada_por_docente__isnull=False,
    ).count()

    if (
        total_obligatorias == 0
        or completadas != total_obligatorias
    ):
        messages.error(
            request,
            "Debes completar todas las actividades obligatorias antes de completar la Ruta.",
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    # Captura del estado previo a la modificacion
    estado_anterior = seccion_ruta.estado

    seccion_ruta.estado = "COMPLETADA"
    seccion_ruta.cerrada_por_docente = docente
    seccion_ruta.fecha_cierre = timezone.now()
    seccion_ruta.porcentaje_final = Decimal("100.00")

    seccion_ruta.save(
        update_fields=[
            "estado",
            "cerrada_por_docente",
            "fecha_cierre",
            "porcentaje_final",
        ]
    )

    registrar_auditoria(
        request=request,
        entidad="SeccionRuta",
        entidad_id=seccion_ruta.pk,
        accion="COMPLETAR_RUTA",
        valores_anteriores={"estado": estado_anterior},
        valores_nuevos={
            "estado": seccion_ruta.estado,
            "fecha_cierre": str(seccion_ruta.fecha_cierre),
            "porcentaje_final": str(seccion_ruta.porcentaje_final),
        },
    )

    messages.success(
        request,
        "La Ruta A+S fue completada correctamente.",
    )

    return redirect(
        "rutas:detalle_ruta_docente",
        seccion_ruta_id=seccion_ruta.id,
    )


@login_required
@require_POST
def subir_evidencia(request, actividad_id):
    actividad = get_object_or_404(
        SeccionActividad.objects.select_related(
            "seccion_ruta",
            "seccion_ruta__seccion",
            "ruta_actividad",
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

    if seccion_ruta.estado == "COMPLETADA":
        messages.error(
            request,
            "La Ruta ya está completada y no puede modificarse.",
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    if actividad.ruta_actividad.orden not in [
        11,
        16,
        20,
        21,
    ]:
        raise PermissionDenied

    if actividad.completada_por_docente_id is not None:
        messages.error(
            request,
            "No puedes subir evidencias a una actividad completada.",
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    archivo_subido = request.FILES.get(
        "archivo"
    )

    if archivo_subido is None:
        messages.error(
            request,
            "Debes seleccionar un archivo.",
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    descripcion = request.POST.get(
        "descripcion",
        "",
    ).strip()

    cantidad_actual = actividad.evidencias.count()

    try:
        validar_cantidad_archivos(
            cantidad_actual,
            1,
        )

        with transaction.atomic():
            expediente, _ = ExpedienteSeccion.objects.get_or_create(
                seccion=seccion_ruta.seccion,
                defaults={
                    "estado": "ABIERTO",
                    "fecha_creacion": timezone.now(),
                },
            )

            archivo = guardar_archivo(
                archivo_subido,
                autor=request.user,
            )

            evidencia = Evidencia.objects.create(
                expediente=expediente,
                seccion_actividad=actividad,
                archivo=archivo,
                descripcion=descripcion or None,
            )

            registrar_auditoria(
                request=request,
                entidad="Evidencia",
                entidad_id=evidencia.pk,
                accion="SUBIR_EVIDENCIA",
                valores_nuevos={
                    "actividad_id": actividad.pk,
                    "archivo": archivo.nombre_original,
                },
            )

    except ValidationError as error:
        messages.error(
            request,
            error.messages[0],
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    messages.success(
        request,
        "La evidencia fue subida correctamente.",
    )

    return redirect(
        "rutas:detalle_ruta_docente",
        seccion_ruta_id=seccion_ruta.id,
    )


@login_required
@require_POST
def eliminar_evidencia(request, evidencia_id):
    evidencia = get_object_or_404(
        Evidencia.objects.select_related(
            "archivo",
            "seccion_actividad",
            "seccion_actividad__seccion_ruta",
            "seccion_actividad__seccion_ruta__seccion",
        ),
        id=evidencia_id,
    )

    actividad = evidencia.seccion_actividad
    seccion_ruta = actividad.seccion_ruta

    verificar_acceso_ruta(
        request.user,
        seccion_ruta,
    )

    if not es_docente(request.user):
        raise PermissionDenied

    if seccion_ruta.estado == "COMPLETADA":
        messages.error(
            request,
            "La Ruta ya está completada y no puede modificarse.",
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    if actividad.completada_por_docente_id is not None:
        messages.error(
            request,
            "No puedes eliminar evidencias de una actividad completada.",
        )

        return redirect(
            "rutas:detalle_ruta_docente",
            seccion_ruta_id=seccion_ruta.id,
        )

    if evidencia.archivo.cargado_por_usuario_id != request.user.id:
        raise PermissionDenied

    archivo = evidencia.archivo
    storage_key = archivo.storage_key
    evidencia_id_backup = evidencia.pk

    evidencia.delete()
    archivo.delete()

    storage = obtener_storage_privado()

    if storage.exists(storage_key):
        storage.delete(storage_key)

    registrar_auditoria(
        request=request,
        entidad="Evidencia",
        entidad_id=evidencia_id_backup,
        accion="ELIMINAR_EVIDENCIA",
        valores_anteriores={"actividad_id": actividad.pk},
    )

    messages.success(
        request,
        "La evidencia fue eliminada correctamente.",
    )

    return redirect(
        "rutas:detalle_ruta_docente",
        seccion_ruta_id=seccion_ruta.id,
    )


@login_required
def seguimiento_rutas_coordinacion(request):
    if not es_coordinador(request.user):
        raise PermissionDenied

    campus_id = request.GET.get("campus", "").strip()
    sede_id = request.GET.get("sede", "").strip()
    periodo_id = request.GET.get("periodo", "").strip()
    estado_filtro = request.GET.get("estado", "").strip()

    rutas = (
        SeccionRuta.objects
        .select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
            "seccion__campus",
            "seccion__campus__sede",
            "cerrada_por_docente",
        )
        .prefetch_related(
            "seccion__docentes",
            "actividades",
            "actividades__ruta_actividad",
        )
        .order_by(
            "seccion__asignatura__nombre",
            "seccion__nrc",
        )
    )

    if campus_id:
        rutas = rutas.filter(seccion__campus_id=campus_id)

    if sede_id:
        rutas = rutas.filter(seccion__campus__sede_id=sede_id)

    if periodo_id:
        rutas = rutas.filter(seccion__periodo_id=periodo_id)

    if estado_filtro:
        rutas = rutas.filter(estado=estado_filtro)

    for ruta in rutas:
        acts = list(ruta.actividades.all())
        total_acts = len(acts)
        completadas = sum(1 for a in acts if a.completada_por_docente_id is not None)
        ruta.total_actividades = total_acts
        ruta.total_completadas = completadas
        ruta.actividades_pendientes = total_acts - completadas

    sedes_list = Sede.objects.all().order_by("nombre")
    campus_list = Campus.objects.all().order_by("nombre")

    return render(
        request,
        "rutas/seguimiento_coordinacion.html",
        {
            "rutas": rutas,
            "sedes": sedes_list,
            "campus_list": campus_list,
            "filtros_seleccionados": {
                "campus": campus_id,
                "sede": sede_id,
                "periodo": periodo_id,
                "estado": estado_filtro,
            },
        },
    )


@login_required
def detalle_ruta_coordinacion(request, seccion_ruta_id):
    if not es_coordinador(request.user):
        raise PermissionDenied

    seccion_ruta = get_object_or_404(
        SeccionRuta.objects.select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
            "seccion__campus",
            "seccion__campus__sede",
            "ruta_version",
            "cerrada_por_docente",
        ).prefetch_related(
            "seccion__docentes",
        ),
        id=seccion_ruta_id,
    )

    actividades = (
        SeccionActividad.objects
        .filter(
            seccion_ruta=seccion_ruta,
        )
        .select_related(
            "ruta_actividad",
            "completada_por_docente",
        )
        .prefetch_related(
            "evidencias__archivo",
        )
        .order_by(
            "ruta_actividad__orden",
        )
    )

    etapas = {}

    for actividad in actividades:
        etapa = actividad.ruta_actividad.etapa

        if etapa not in etapas:
            etapas[etapa] = []

        etapas[etapa].append(actividad)

    total_actividades = actividades.count()

    total_completadas = actividades.filter(
        completada_por_docente__isnull=False,
    ).count()

    total_pendientes = (
        total_actividades
        - total_completadas
    )

    return render(
        request,
        "rutas/detalle_ruta_coordinacion.html",
        {
            "seccion_ruta": seccion_ruta,
            "seccion": seccion_ruta.seccion,
            "etapas": etapas,
            "total_actividades": total_actividades,
            "total_completadas": total_completadas,
            "total_pendientes": total_pendientes,
        },
    )