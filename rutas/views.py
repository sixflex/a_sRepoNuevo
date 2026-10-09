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
from usuarios.permissions import es_coordinador, es_docente

from .models import Evidencia, ExpedienteSeccion, SeccionActividad, SeccionRuta
from django.urls import reverse
from encuestas.models import EnlaceFormulario
from encuestas import services as encuestas_services


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
    formularios_por_actividad = {
        19: [
            "EVALUACION_AS_ESTUDIANTES",
            "EVALUACION_AS_DOCENTES",
            "EVALUACION_AS_SOCIOS",
        ],
        23: [
            "RESUMEN_IMPLEMENTACION_DOCENTE",
        ],
    }

    codigos = [
        codigo
        for lista in formularios_por_actividad.values()
        for codigo in lista
    ]

    enlaces = (
        EnlaceFormulario.objects
        .filter(
            version__plantilla__codigo__in=codigos,
            activo=True,
            seccion__isnull=True,
        )
        .select_related("version__plantilla")
        .order_by("id")
    )

    enlaces_por_codigo = {}

    for enlace in enlaces:
        if (
            enlace.version.plantilla.codigo not in enlaces_por_codigo
            and encuestas_services.enlace_abierto(enlace)
        ):
            enlaces_por_codigo[enlace.version.plantilla.codigo] = enlace

    for actividad in actividades:
        actividad.formularios_ruta = []

        for codigo in formularios_por_actividad.get(
            actividad.ruta_actividad.orden, []
        ):
            enlace = enlaces_por_codigo.get(codigo)

            if enlace:
                actividad.formularios_ruta.append({
                    "nombre": enlace.version.plantilla.titulo,
                    "url": reverse(
                        "encuestas:responder",
                        args=[enlace.token],
                    ),
                })
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

    if actividad.completada_por_docente_id is None:
        actividad.completada_por_docente = docente
        actividad.estado = "COMPLETADA"
        actividad.fecha_completada = timezone.now()
    else:
        actividad.completada_por_docente = None
        actividad.estado = "PENDIENTE"
        actividad.fecha_completada = None

    actividad.save(
        update_fields=[
            "completada_por_docente",
            "estado",
            "fecha_completada",
        ]
    )

    recalcular_avance(
        seccion_ruta
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

            Evidencia.objects.create(
                expediente=expediente,
                seccion_actividad=actividad,
                archivo=archivo,
                descripcion=descripcion or None,
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

    evidencia.delete()
    archivo.delete()

    storage = obtener_storage_privado()

    if storage.exists(storage_key):
        storage.delete(storage_key)

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
        )
        .order_by(
            "seccion__asignatura__nombre",
            "seccion__nrc",
        )
    )

    return render(
        request,
        "rutas/seguimiento_coordinacion.html",
        {
            "rutas": rutas,
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