import tempfile
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from archivos.services import guardar_archivo, obtener_storage_privado
from archivos.validators import validar_cantidad_archivos
from auditoria.services import registrar_auditoria
from academico.models import Campus, Docente, PeriodoAcademico, Sede
from auditoria.services import registrar_auditoria
from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_required
from . import paso_a_paso
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


# Desde dónde abrió el Docente su Ruta, para que "Volver" lo devuelva ahí.
# Se recuerda en la sesión porque marcar actividades o subir evidencias
# vuelve a esta página sin el parámetro.
ORIGENES_RUTA = {"inicio": "Volver al inicio", "seccion": "Volver a la sección"}


def _volver_ruta_docente(request, seccion_ruta):
    clave = f"ruta_docente_desde_{seccion_ruta.pk}"
    desde = request.GET.get("desde")
    if desde in ORIGENES_RUTA:
        request.session[clave] = desde
    else:
        desde = request.session.get(clave, "seccion")
    if desde == "inicio":
        return reverse("core:inicio_docente"), ORIGENES_RUTA["inicio"]
    return reverse("core:detalle_seccion", args=[seccion_ruta.seccion_id]), ORIGENES_RUTA["seccion"]


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

    # Paso a paso: una acción por actividad, formularios por sección y
    # precargados (ficha única), y solo la etapa en curso abierta.
    actividades = paso_a_paso.preparar_actividades(request, seccion_ruta, list(actividades))
    etapas, etapa_actual = paso_a_paso.armar_etapas(actividades)
    total_actividades = len(actividades)
    hechas = sum(1 for actividad in actividades if actividad.completada_por_docente_id)

    for actividad in actividades:
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

    url_volver, texto_volver = _volver_ruta_docente(request, seccion_ruta)

    return render(
        request,
        "rutas/detalle_ruta_docente.html",
        {
            "url_volver": url_volver,
            "texto_volver": texto_volver,
            "seccion_ruta": seccion_ruta,
            "seccion": seccion_ruta.seccion,
            "etapas": etapas,
            "etapa_actual": etapa_actual,
            "ruta_abierta": seccion_ruta.estado != "COMPLETADA",
            "total_actividades": total_actividades,
            "actividades_hechas": hechas,
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

        if actividad.observacion == servicios.OBSERVACION_SIN_CIERRE:
            actividad.observacion = ""

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
            "fecha_completada": (
                fecha_completada_anterior.isoformat()
                if fecha_completada_anterior
                else None
            ),
        },
        valores_nuevos={
            "estado": actividad.estado,
            "fecha_completada": (
                actividad.fecha_completada.isoformat()
                if actividad.fecha_completada
                else None
            ),
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
    docente_id = request.GET.get("docente", "").strip()
    vista = "docentes" if request.GET.get("vista") == "docentes" else "secciones"

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

    # Pestaña "Por docente": promedio de todas las Rutas de cada docente con
    # los mismos filtros. Al tocar un docente se ven sus secciones.
    por_docente = servicios.promedio_por_docente(rutas.order_by()) if vista == "docentes" else []

    docente_filtrado = None
    if docente_id.isdigit():
        docente_filtrado = Docente.objects.filter(pk=docente_id).first()
        rutas = rutas.filter(seccion__docentes__id=docente_id)

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
            "vista": vista,
            "por_docente": por_docente,
            "docente_filtrado": docente_filtrado,
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

    # Vista simple: avance, etapa en curso y una fila por etapa con lo pendiente.
    lista = list(actividades)
    etapas, etapa_actual = paso_a_paso.armar_etapas(lista)
    total_actividades = len(lista)
    total_completadas = sum(1 for actividad in lista if actividad.completada_por_docente_id)
    total_pendientes = total_actividades - total_completadas

    return render(
        request,
        "rutas/detalle_ruta_coordinacion.html",
        {
            "seccion_ruta": seccion_ruta,
            "seccion": seccion_ruta.seccion,
            "etapas": etapas,
            "etapa_actual": etapa_actual,
            "docentes": ", ".join(str(d) for d in seccion_ruta.seccion.docentes.all()),
            "observacion_sin_cierre": servicios.OBSERVACION_SIN_CIERRE,
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
            "ficha_disponible": servicios.ficha_disponible(seccion_ruta),
        },
    )




@login_required
def encuesta_socios(request):
    """
    Envío masivo de la encuesta de satisfacción a los Socios Comunitarios del
    período (lo hace el Coordinador una vez, al final del semestre).
    """
    if not es_coordinador(request.user):
        raise PermissionDenied

    from core.indicadores import filtros_inicio

    from . import encuesta_socios as encuesta

    periodos = PeriodoAcademico.objects.order_by("-anio", "-id")
    elegido = request.POST.get("periodo") or request.GET.get("periodo") or filtros_inicio({}).get("periodo")
    periodo = periodos.filter(pk=elegido).first() if str(elegido or "").isdigit() else None
    periodo = periodo or periodos.first()

    if request.method == "POST" and periodo is not None:
        resumen = encuesta.enviar(periodo, request, reenviar=request.POST.get("reenviar") == "1")
        if resumen is None:
            messages.error(request, "La encuesta de socios no está publicada. Publícala en Formularios y encuestas.")
        else:
            if resumen["enviados"]:
                messages.success(request, f"Encuesta enviada a {resumen['enviados']} socio{'s' if resumen['enviados'] != 1 else ''}.")
            elif not resumen["errores"]:
                messages.info(request, "No había socios por enviar: ya la recibieron o respondieron.")
            if resumen["errores"]:
                messages.error(request, "No se pudo enviar a: " + ", ".join(resumen["errores"]) + ". Puedes intentarlo de nuevo.")
            registrar_auditoria(
                request=request,
                entidad="PeriodoAcademico",
                entidad_id=periodo.pk,
                accion="ENVIAR_ENCUESTA_SOCIOS",
                valores_nuevos={
                    "enviados": resumen["enviados"],
                    "errores": resumen["errores"],
                    "sin_correo": resumen["sin_correo"],
                },
            )
        return redirect(f"{reverse('rutas:encuesta_socios')}?periodo={periodo.pk}")

    version, filas = encuesta.estado_envio(periodo) if periodo else (None, [])
    return render(
        request,
        "rutas/encuesta_socios.html",
        {
            "periodos": periodos,
            "periodo": periodo,
            "version": version,
            "filas": filas,
            "por_enviar": sum(1 for f in filas if f["correo"] and not f["enviado"] and not f["respondio"]),
            "enviados": sum(1 for f in filas if f["enviado"]),
            "respondieron": sum(1 for f in filas if f["respondio"]),
            "sin_correo": sum(1 for f in filas if not f["correo"]),
        },
    )


@login_required
def formularios_qr(request):
    if not (es_docente(request.user) or es_coordinador(request.user)):
        raise PermissionDenied

    proceso = request.GET.get("proceso", "").strip()
    formularios = servicios.formularios_qr_de_proceso(request, proceso)

    # Volver a la Ruta si se llegó desde ella (?ruta=<id>); si no, a mis secciones.
    url_volver, texto_volver = reverse("core:docente"), "Volver a mis secciones"
    ruta_id = request.GET.get("ruta", "")
    if ruta_id.isdigit():
        seccion_ruta = SeccionRuta.objects.filter(pk=ruta_id).select_related("seccion").first()
        if seccion_ruta is not None:
            try:
                verificar_acceso_ruta(request.user, seccion_ruta)
            except PermissionDenied:
                pass
            else:
                url_volver = reverse("rutas:detalle_ruta_docente", args=[seccion_ruta.id])
                texto_volver = "Volver a la Ruta"

    return render(
        request,
        "rutas/formularios_qr.html",
        {
            "formularios": formularios,
            "url_volver": url_volver,
            "texto_volver": texto_volver,
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


def _ficha_coordinacion_o_403(request, seccion_ruta_id):
    """La ficha completa es solo del Coordinador y solo con la Ruta completada."""
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

    if not servicios.ficha_disponible(seccion_ruta):
        raise PermissionDenied("La ficha se puede ver cuando el docente complete la Ruta.")
    return seccion_ruta


@login_required
def ver_ficha_coordinacion(request, seccion_ruta_id):
    """
    Ficha del proyecto en el navegador, con todo lo que llenó el docente:
    cada formulario con sus preguntas y respuestas. Se exporta a Excel.
    """
    seccion_ruta = _ficha_coordinacion_o_403(request, seccion_ruta_id)
    from .ficha import datos_ficha

    registrar_auditoria(
        request=request,
        entidad="SeccionRuta",
        entidad_id=seccion_ruta.pk,
        accion="VER_FICHA_PROYECTO",
        valores_nuevos={},
    )
    return render(request, "rutas/ficha_coordinacion.html", {
        "seccion_ruta": seccion_ruta,
        **datos_ficha(seccion_ruta),
    })


@login_required
def exportar_ficha_excel(request, seccion_ruta_id):
    seccion_ruta = _ficha_coordinacion_o_403(request, seccion_ruta_id)
    from core import excel
    from .ficha import generar_ficha_excel

    registrar_auditoria(
        request=request,
        entidad="SeccionRuta",
        entidad_id=seccion_ruta.pk,
        accion="EXPORTAR_FICHA_PROYECTO",
        valores_nuevos={},
    )
    nombre = f"Ficha del proyecto - NRC {seccion_ruta.seccion.nrc}.xlsx"
    return excel.respuesta_excel(generar_ficha_excel(seccion_ruta), nombre)


@login_required
def descargar_mi_carpeta(request, seccion_ruta_id):
    """
    El docente descarga la carpeta que se armó con lo que subió en la Ruta
    (actividad 22), la misma que ve Coordinación.
    """
    seccion_ruta = get_object_or_404(
        SeccionRuta.objects.select_related("seccion__asignatura", "seccion__periodo"),
        id=seccion_ruta_id,
    )
    verificar_acceso_ruta(request.user, seccion_ruta)
    expediente = ExpedienteSeccion.objects.filter(seccion=seccion_ruta.seccion).first()
    destino = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024)
    servicios.generar_zip_expediente(expediente, destino, seccion_ruta=seccion_ruta)
    destino.seek(0)
    return FileResponse(
        destino, as_attachment=True,
        filename=servicios.nombre_zip_expediente(seccion_ruta.seccion), content_type="application/zip",
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

    # Aunque aún no haya evidencias, el ZIP trae la ficha del proyecto.
    nombre = servicios.nombre_zip_expediente(seccion)
    destino = tempfile.SpooledTemporaryFile(max_size=50 * 1024 * 1024)
    faltantes = servicios.generar_zip_expediente(expediente, destino, seccion_ruta=seccion_ruta)
    destino.seek(0)

    registrar_auditoria(
        request=request,
        entidad="ExpedienteSeccion" if expediente else "SeccionRuta",
        entidad_id=expediente.pk if expediente else seccion_ruta.pk,
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


@login_required
def descargar_acuerdo(request, actividad_id):
    """
    Acuerdo formal en PDF para imprimir y firmar (actividad 11): el que llenó
    el docente (?respuesta=<id>) o el formato en blanco.
    """
    from encuestas.models import RespuestaFormulario
    from encuestas.precarga import FORMALIZACION_ACUERDOS

    from .acuerdo import construir_pdf_acuerdo

    actividad = get_object_or_404(
        SeccionActividad.objects.select_related(
            "seccion_ruta__seccion__asignatura",
            "seccion_ruta__seccion__periodo",
            "ruta_actividad__formulario_version__plantilla",
        ),
        id=actividad_id,
    )
    verificar_acceso_ruta(request.user, actividad.seccion_ruta)
    seccion = actividad.seccion_ruta.seccion

    respuesta = None
    if request.GET.get("respuesta"):
        respuesta = get_object_or_404(
            RespuestaFormulario.objects.select_related("version__plantilla"),
            pk=request.GET["respuesta"],
            seccion=seccion,
            version__plantilla__codigo=FORMALIZACION_ACUERDOS,
        )
        version = respuesta.version
    else:
        version = paso_a_paso._version_formulario(actividad.ruta_actividad, {})
        if version is None or version.plantilla.codigo != FORMALIZACION_ACUERDOS:
            raise Http404("Esta actividad no tiene acuerdo formal.")

    pdf = construir_pdf_acuerdo(seccion, version, respuesta)
    nombre = "Acuerdo formal A+S.pdf" if respuesta else "Acuerdo formal A+S (en blanco).pdf"
    respuesta_http = HttpResponse(pdf, content_type="application/pdf")
    respuesta_http["Content-Disposition"] = f'inline; filename="{nombre}"'
    return respuesta_http
