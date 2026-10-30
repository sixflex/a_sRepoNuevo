import tempfile
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from archivos.services import guardar_archivo, obtener_storage_privado
from archivos.validators import validar_cantidad_archivos
from auditoria.services import registrar_auditoria
from academico.models import Campus, PeriodoAcademico, Sede
from auditoria.services import registrar_auditoria
from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_required
from . import services as servicios
from .models import Evidencia, ExpedienteSeccion, SeccionActividad, SeccionRuta
from django.urls import reverse
from core.qr import qr_base64
from encuestas.models import FormularioPlantilla

from . import services as servicios
from .services import enlaces_abiertos_por_plantilla, url_recurso
from socios.models import InvitacionCierre

from academico.models import Sede, Campus, PeriodoAcademico
from .models import Evidencia, ExpedienteSeccion, SeccionActividad, SeccionRuta, RutaVersion

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

    if seccion_ruta.estado != "COMPLETADA":
        recalcular_avance(seccion_ruta)

    actividades = (
        SeccionActividad.objects
        .filter(
            seccion_ruta=seccion_ruta,
        )
        .select_related(
            "seccion_ruta",
            "ruta_actividad",
            "ruta_actividad__archivo_recurso",
            "ruta_actividad__formulario_version",
            "ruta_actividad__formulario_version__plantilla",
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
    enlaces_por_plantilla = enlaces_abiertos_por_plantilla({
        actividad.ruta_actividad.formulario_version.plantilla_id
        for actividad in actividades
        if actividad.ruta_actividad.formulario_version_id
    })
    
    plantillas_encuestas = FormularioPlantilla.objects.filter(
        versiones__id__in=[3, 4, 5],
        versiones__estado="PUBLICADA",
        activo=True,
    ).distinct().order_by("titulo")

    enlaces_encuestas = enlaces_abiertos_por_plantilla(
        list(plantillas_encuestas.values_list("id", flat=True))
    )

    encuestas_as = [
        {
            "titulo": plantilla.titulo,
            "token": enlaces_encuestas[plantilla.id].token,
        }
        for plantilla in plantillas_encuestas
        if plantilla.id in enlaces_encuestas
    ]


    for actividad in actividades:
        actividad.url_recurso = url_recurso(actividad)
        actividad.encuestas_as = (
            encuestas_as
            if seccion_ruta.ruta_version.numero_version == 2
            and actividad.ruta_actividad.orden == 19
            else []
        )
        actividad.enlace_formulario = (
            enlaces_por_plantilla.get(
                actividad.ruta_actividad.formulario_version.plantilla_id
            )
            if actividad.ruta_actividad.formulario_version_id
            else None
        )
        actividad.formulario_compartible = None
        actividad.formulario_directo = None

        if (
            seccion_ruta.ruta_version.numero_version == 2
            and actividad.ruta_actividad.orden in (5, 13)
            and actividad.ruta_actividad.formulario_version_id
        ):
            from rutas.services import obtener_o_crear_enlace_seccion

            enlace_seccion = obtener_o_crear_enlace_seccion(
                version_formulario=actividad.ruta_actividad.formulario_version,
                seccion=seccion_ruta.seccion,
                usuario=request.user,
            )

            actividad.enlace_formulario = enlace_seccion

            if enlace_seccion is not None:
                url_formulario = request.build_absolute_uri(
                    reverse(
                        "encuestas:responder",
                        args=[enlace_seccion.token],
                    )
                )

                if actividad.ruta_actividad.orden == 5:
                    actividad.formulario_directo = url_formulario

                elif actividad.ruta_actividad.orden == 13:
                    actividad.formulario_compartible = {
                        "url": url_formulario,
                        "qr_base64": qr_base64(url_formulario),
                    }
        actividad.es_cierre = servicios.es_actividad_cierre(
            actividad.ruta_actividad
        )

        if actividad.es_cierre:
            actividad.invitaciones = list(
                seccion_ruta.invitaciones_cierre
                .select_related("socio")
                .order_by("socio__nombre_organizacion")
            )
            actividad.socios_por_invitar = (
                servicios.socios_de_seccion(seccion_ruta.seccion)
                .exclude(invitaciones_cierre__seccion_ruta=seccion_ruta)
            )

    return render(
        request,
        "rutas/detalle_ruta_docente.html",
        {
            "seccion_ruta": seccion_ruta,
            "seccion": seccion_ruta.seccion,
            "etapas": etapas,
            "puede_completar_ruta": puede_completar_ruta,
            "observacion_sin_cierre": servicios.OBSERVACION_SIN_CIERRE,
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
    fecha_completada_anterior = actividad.fecha_completada

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
            "observacion",
        ]
    )

    registrar_auditoria(
        request=request,
        entidad="SeccionActividad",
        entidad_id=actividad.pk,
        accion="CAMBIAR_ESTADO_ACTIVIDAD",
        valores_anteriores={
            "estado": estado_anterior,
            "fecha_completada": fecha_completada_anterior.isoformat() if fecha_completada_anterior else None,
        },
        valores_nuevos={
            "estado": actividad.estado,
            "fecha_completada": str(actividad.fecha_completada) if actividad.fecha_completada else None,
        },
    )

    recalcular_avance(seccion_ruta)
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

    registrar_auditoria(
        request=request,
        entidad="Evidencia",
        entidad_id=evidencia.pk,
        accion="ELIMINAR_EVIDENCIA",
        valores_anteriores={
            "evidencia_id": evidencia.pk,
            "archivo_id": archivo.pk,
            "actividad_id": actividad.pk,
            "descripcion": evidencia.descripcion,
        },
    )

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
    periodos_list = PeriodoAcademico.objects.all().order_by("-nombre")

    return render(
        request,
        "rutas/seguimiento_coordinacion.html",
        {
            "rutas": rutas,
            "sedes": sedes_list,
            "campus_list": campus_list,
            "periodos": periodos_list,
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

    if seccion_ruta.estado != "COMPLETADA":
        recalcular_avance(seccion_ruta)

    actividades = (
        SeccionActividad.objects
        .filter(
            seccion_ruta=seccion_ruta,
        )
        .select_related(
            "ruta_actividad",
            "ruta_actividad__archivo_recurso",
            "ruta_actividad__formulario_version",
            "ruta_actividad__formulario_version__plantilla",
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
            "invitaciones_cierre": (
                seccion_ruta.invitaciones_cierre
                .select_related("socio")
                .order_by("socio__nombre_organizacion")
            ),
            "sin_cierre": actividades.filter(
                observacion=servicios.OBSERVACION_SIN_CIERRE,
            ).exists(),
        },
    )




@login_required
def formularios_qr(request):
    if not (es_docente(request.user) or es_coordinador(request.user)):
        raise PermissionDenied

    proceso = request.GET.get("proceso", "").strip()

    plantillas = FormularioPlantilla.objects.filter(
        proceso=proceso,
        activo=True,
    ).order_by("titulo")

    enlaces = enlaces_abiertos_por_plantilla(
        plantillas.values_list("id", flat=True)
    )

    formularios = []

    for plantilla in plantillas:
        enlace = enlaces.get(plantilla.id)

        if enlace is None:
            continue

        url = request.build_absolute_uri(
            reverse("encuestas:responder", args=[enlace.token])
        )

        formularios.append({
            "titulo": plantilla.titulo,
            "url": url,
            "qr_base64": qr_base64(url),
        })

    return render(
        request,
        "rutas/formularios_qr.html",
        {
            "formularios": formularios,
        },
    )


def _actividad_cierre_del_docente(request, actividad_id):
    actividad = get_object_or_404(
        SeccionActividad.objects.select_related(
            "seccion_ruta",
            "seccion_ruta__seccion",
            "ruta_actividad",
        ),
        id=actividad_id,
    )

    verificar_acceso_ruta(request.user, actividad.seccion_ruta)

    docente = getattr(request.user, "perfil_docente", None)

    if not es_docente(request.user) or docente is None:
        raise PermissionDenied

    if not servicios.es_actividad_cierre(actividad.ruta_actividad):
        raise PermissionDenied

    return actividad, docente


def _volver_a_ruta(seccion_ruta):
    return redirect(
        "rutas:detalle_ruta_docente",
        seccion_ruta_id=seccion_ruta.id,
    )


def _envio_ok(envio):
    return envio is not None and envio.resultado == "OK"


@login_required
@require_POST
def indicar_sin_cierre(request, actividad_id):
    actividad, docente = _actividad_cierre_del_docente(request, actividad_id)
    seccion_ruta = actividad.seccion_ruta

    if seccion_ruta.estado == "COMPLETADA":
        messages.error(request, "La Ruta ya está completada y no puede modificarse.")
        return _volver_a_ruta(seccion_ruta)

    if seccion_ruta.invitaciones_cierre.exists():
        messages.error(
            request,
            "Ya hay Socios invitados a la actividad de cierre.",
        )
        return _volver_a_ruta(seccion_ruta)

    servicios.indicar_sin_cierre(actividad, docente, request)
    recalcular_avance(seccion_ruta)

    messages.success(request, "Se registró que no habrá actividad de cierre.")

    return _volver_a_ruta(seccion_ruta)


@login_required
@require_POST
def invitar_socios_cierre(request, actividad_id):
    actividad, _docente = _actividad_cierre_del_docente(request, actividad_id)
    seccion_ruta = actividad.seccion_ruta

    if seccion_ruta.estado == "COMPLETADA":
        messages.error(request, "La Ruta ya está completada y no puede modificarse.")
        return _volver_a_ruta(seccion_ruta)

    modo = request.POST.get("modo_contacto")

    if modo not in (servicios.MODO_PLATAFORMA, servicios.MODO_EXTERNO):
        messages.error(request, "Indica cómo contactarás al Socio Comunitario.")
        return _volver_a_ruta(seccion_ruta)

    socios = servicios.socios_de_seccion(seccion_ruta.seccion).filter(
        id__in=request.POST.getlist("socios")
    )

    if not socios:
        messages.error(request, "Selecciona al menos un Socio Comunitario.")
        return _volver_a_ruta(seccion_ruta)

    invitaciones = servicios.crear_invitaciones_cierre(
        seccion_ruta,
        socios,
        modo,
        request,
    )

    if modo == servicios.MODO_EXTERNO:
        messages.success(
            request,
            "Invitación registrada. Recuerda anotar si el Socio asistirá.",
        )
        return _volver_a_ruta(seccion_ruta)

    sin_envio = [
        invitacion.socio.nombre_organizacion
        for invitacion in invitaciones
        if not _envio_ok(servicios.enviar_invitacion_cierre(invitacion, request))
    ]

    if sin_envio:
        messages.warning(
            request,
            "No se pudo enviar la invitación a: "
            + ", ".join(sin_envio)
            + ". Revisa su correo de contacto y reintenta.",
        )
    else:
        messages.success(request, "Invitación enviada por correo.")

    return _volver_a_ruta(seccion_ruta)


def _invitacion_del_docente(request, invitacion_id):
    invitacion = get_object_or_404(
        InvitacionCierre.objects.select_related(
            "socio",
            "seccion_ruta",
            "seccion_ruta__seccion",
        ),
        id=invitacion_id,
    )

    verificar_acceso_ruta(request.user, invitacion.seccion_ruta)

    if not es_docente(request.user):
        raise PermissionDenied

    return invitacion


@login_required
@require_POST
def reenviar_invitacion_cierre(request, invitacion_id):
    invitacion = _invitacion_del_docente(request, invitacion_id)

    if invitacion.modo_contacto != servicios.MODO_PLATAFORMA:
        raise PermissionDenied

    if _envio_ok(servicios.enviar_invitacion_cierre(invitacion, request)):
        messages.success(request, "Invitación enviada por correo.")
    else:
        messages.warning(
            request,
            "No se pudo enviar la invitación. Revisa el correo de contacto del Socio.",
        )

    return _volver_a_ruta(invitacion.seccion_ruta)


@login_required
@require_POST
def registrar_respuesta_cierre(request, invitacion_id):
    """Contacto externo: el Docente anota el resultado (RF-EVI-05)."""
    invitacion = _invitacion_del_docente(request, invitacion_id)
    respuesta = request.POST.get("respuesta")

    if respuesta not in servicios.ETIQUETAS_RESPUESTA:
        messages.error(request, "Respuesta no válida.")
    else:
        servicios.registrar_respuesta_cierre(invitacion, respuesta, request)
        messages.success(request, "Respuesta del Socio registrada.")

    return _volver_a_ruta(invitacion.seccion_ruta)

RESPUESTAS_ENLACE = {
    "asistire": servicios.ASISTIRA,
    "no-asistire": servicios.NO_ASISTIRA,
}


def responder_invitacion_cierre(request, token, respuesta):
    if respuesta not in RESPUESTAS_ENLACE:
        raise Http404

    invitacion = get_object_or_404(
        InvitacionCierre.objects.select_related(
            "socio",
            "seccion_ruta__seccion__asignatura",
            "seccion_ruta__seccion__campus__sede",
            "seccion_ruta__seccion__periodo",
        ),
        token=token,
    )

    registrada = False

    if request.method == "POST":
        correo = servicios.correo_contacto_principal(invitacion.socio)
        servicios.registrar_respuesta_cierre(
            invitacion,
            RESPUESTAS_ENLACE[respuesta],
            request,
            actor_externo=correo or invitacion.socio.nombre_organizacion,
        )
        registrada = True

    seccion = invitacion.seccion_ruta.seccion

    return render(
        request,
        "rutas/responder_invitacion_cierre.html",
        {
            "invitacion": invitacion,
            "seccion": seccion,
            "carreras": ", ".join(
                seccion.carreras.values_list("nombre", flat=True)
            ),
            "asistira": RESPUESTAS_ENLACE[respuesta] == servicios.ASISTIRA,
            "registrada": registrada,
            "hide_sidebar": True,
        },
    )


@login_required
def descargar_expediente(request, seccion_ruta_id):
    if not es_coordinador(request.user):
        raise PermissionDenied

    seccion_ruta = get_object_or_404(
        SeccionRuta.objects.select_related(
            "seccion__asignatura",
            "seccion__periodo",
            "seccion__campus__sede",
        ),
        id=seccion_ruta_id,
    )

    seccion = seccion_ruta.seccion
    expediente = ExpedienteSeccion.objects.filter(seccion=seccion).first()

    if expediente is None or not expediente.evidencias.exists():
        messages.info(request, "Esta sección todavía no tiene evidencias cargadas.")
        return redirect(
            "rutas:detalle_ruta_coordinacion",
            seccion_ruta_id=seccion_ruta.id,
        )

    nombre = servicios.nombre_zip_expediente(seccion)
    destino = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024)
    faltantes = servicios.generar_zip_expediente(expediente, destino)
    destino.seek(0)

    registrar_auditoria(
        request=request,
        entidad="ExpedienteSeccion",
        entidad_id=expediente.pk,
        accion="DESCARGAR_EXPEDIENTE",
        valores_nuevos={
            "archivo_zip": nombre,
            "faltantes": faltantes,
        },
    )

    return FileResponse(
        destino,
        as_attachment=True,
        filename=nombre,
        content_type="application/zip",
    )
