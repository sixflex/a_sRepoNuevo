from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from rutas.services import obtener_recordatorios_ruta
from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_required, docente_required
from core.ordenamiento import OPCIONES_ORDEN, orden_pedido, ordenar_por_fecha

from academico.models import (
    PeriodoAcademico,
    Seccion,
)

def inicio(request):
    if request.user.is_authenticated:
        if es_coordinador(request.user):
            return redirect("core:coordinacion")
        if es_docente(request.user):
            # El inicio del docente es el resumen de sus Rutas A+S;
            # "Mis secciones" (core:docente) queda como opción del menú.
            return redirect("core:inicio_docente")

    # Mapa público (HU-10, RF-PUB-01): solo totales por comuna, sin datos personales.
    from . import indicadores

    filtros = indicadores.filtros_publicos(request.GET)
    return render(request, "core/inicio.html", {
        "filtros": filtros,
        "opciones": indicadores.opciones_publicas(),
        "mapa": indicadores.mapa(filtros),
        "estudiantes": indicadores.estudiantes_participantes(filtros),
    })


@coordinador_required
def panel_coordinacion(request):
    """
    Panel del coordinador (HU-08): indicadores del período, avance de la Ruta
    por carrera, satisfacción, mapa y evolución, con los filtros del panel
    lateral (RF-IND-01). Los cálculos están en core/indicadores.py.
    """
    from cartas.models import SolicitudCarta
    from planificacion.models import Planificacion
    from socios.models import PostulacionSocio

    from . import indicadores

    filtros = indicadores.leer_filtros(request.GET)
    periodo_actual = (
        PeriodoAcademico.objects
        .filter(estado="Activo")
        .order_by("-anio", "-id")
        .first()
    )

    # Pendientes del coordinador: solo flujos que ya existen en el portal.
    pendientes = [
        {
            "label": "Cartas por revisar",
            "value": SolicitudCarta.objects.filter(estado="PENDIENTE").count(),
            "icon": "bi-envelope-paper",
            "url": reverse("cartas:listar_solicitudes_coordinacion"),
        },
        {
            "label": "Planificaciones con filas observadas",
            "value": Planificacion.objects.filter(filas_observadas__gt=0).count(),
            "icon": "bi-exclamation-triangle",
            "url": reverse("core:planificacion_coordinacion"),
        },
        {
            "label": "Postulaciones de socios por revisar",
            "value": PostulacionSocio.objects.filter(estado="RECIBIDA").count(),
            "icon": "bi-person-plus",
            "url": reverse("socios:lista_postulaciones"),
        },
    ]

    chips = indicadores.chips(filtros)
    # El mapa del coordinador sí trae dirección, contacto e intervenciones de cada socio.
    mapa = indicadores.mapa(filtros, detalle=True)

    return render(
        request,
        "core/coordinacion.html",
        {
            "filtros": filtros,
            "chips": chips,
            "cantidad_filtros": len(chips),
            "opciones": indicadores.opciones_filtros(),
            "periodo_actual": periodo_actual,
            "tarjetas": indicadores.tarjetas(filtros),
            "avance_carreras": indicadores.avance_por_carrera(filtros),
            "umbrales": {"medio": indicadores.UMBRAL_MEDIO, "alto": indicadores.UMBRAL_ALTO},
            "pendientes": pendientes,
            "satisfaccion": indicadores.satisfaccion(filtros),
            "mapa": mapa,
            "evolucion": indicadores.evolucion(filtros),
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
    )
    orden = orden_pedido(request)
    planificaciones = ordenar_por_fecha(planificaciones, "fecha_envio_final", orden)

    return render(
        request,
        "core/planificacion_coordinacion.html",
        {
            "planificaciones": planificaciones,
            "orden": orden,
            "opciones_orden": OPCIONES_ORDEN,
        },
    )

@docente_required
def inicio_docente(request):
    from decimal import Decimal
    from rutas.models import SeccionRuta

    secciones = (
        Seccion.objects
        .filter(docentes__usuario=request.user)
        .distinct()
    )

    rutas = list(
        SeccionRuta.objects
        .filter(seccion__docentes__usuario=request.user)
        .select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
        )
        .prefetch_related(
            "actividades__ruta_actividad",
        )
        .distinct()
        .order_by("-seccion__periodo__anio", "seccion__nrc")
    )

    total_secciones = secciones.count()
    rutas_completadas = 0
    total_pendientes = 0
    total_obligatorias = 0
    total_completadas = 0

    recordatorios_por_seccion = obtener_recordatorios_ruta(
        [ruta.seccion for ruta in rutas]
    )

    for ruta in rutas:
        actividades = [
            actividad
            for actividad in ruta.actividades.all()
            if actividad.ruta_actividad.es_obligatoria
        ]

        cantidad_obligatorias = len(actividades)

        cantidad_completadas = sum(
            1
            for actividad in actividades
            if actividad.completada_por_docente_id is not None
        )

        pendientes = cantidad_obligatorias - cantidad_completadas

        ruta.pendientes_obligatorias = pendientes
        ruta.avance_calculado = (
            round(cantidad_completadas * 100 / cantidad_obligatorias, 2)
            if cantidad_obligatorias
            else 0
        )

        recordatorios = recordatorios_por_seccion.get(ruta.seccion_id, [])
        ruta.recordatorios = (
            recordatorios
            if isinstance(recordatorios, list)
            else []
        )

        if ruta.estado == "COMPLETADA":
            rutas_completadas += 1

        total_pendientes += pendientes
        total_obligatorias += cantidad_obligatorias
        total_completadas += cantidad_completadas

    avance_general = (
        round(total_completadas * 100 / total_obligatorias, 2)
        if total_obligatorias
        else 0
    )

    return render(
        request,
        "core/inicio_docente.html",
        {
            "total_secciones": total_secciones,
            "rutas_completadas": rutas_completadas,
            "total_pendientes": total_pendientes,
            "avance_general": avance_general,
            "rutas": rutas,
        },
    )


@docente_required
def panel_docente(request):
    periodos = (
        PeriodoAcademico.objects
        .all()
        .order_by(
            "-anio",
            "tipo",
            "nombre",
        )
    )

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

    periodo_id = request.GET.get("periodo", "").strip()
    periodo_seleccionado = None

    if periodo_id and periodo_id.isdigit():
        secciones = secciones.filter(periodo_id=int(periodo_id))
        periodo_seleccionado = periodos.filter(id=int(periodo_id)).first()
    else:
        periodo_id = ""

    secciones = secciones.order_by(
        "-periodo__anio",
        "periodo__tipo",
        "asignatura__nombre",
        "nrc",
    )

    secciones = list(secciones)
    

    recordatorios = obtener_recordatorios_ruta(secciones)
    for seccion in secciones:
        seccion.recordatorio_ruta = recordatorios.get(seccion.id)


    return render(
        request,
        "core/docente.html",
        {
            "secciones": secciones,
            "periodos": periodos,
            "periodo_id": periodo_id,
            "periodo_seleccionado": periodo_seleccionado,
        },
    )

@login_required
def detalle_seccion(request, seccion_id):
    """
    Ficha única de la sección para ambos roles. El docente ve sus
    herramientas (registro de equipos, equipos y Ruta); el coordinador ve
    además los docentes y consulta equipos y Ruta en modo lectura, sin
    botones que lo lleven a páginas exclusivas del docente.
    """
    seccion = get_object_or_404(
        Seccion.objects
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .prefetch_related(
            "docentes",
            "seccion_carreras__carrera__facultad",
            "seccion_docentes__docente",
        ),
        id=seccion_id,
    )

    vista_coordinador = es_coordinador(request.user)

    if vista_coordinador:
        pass

    elif es_docente(request.user):
        pertenece_al_docente = seccion.docentes.filter(
            usuario=request.user
        ).exists()

        if not pertenece_al_docente:
            raise PermissionDenied

    else:
        raise PermissionDenied

    equipos = None

    if vista_coordinador:
        equipos = (
            seccion.equipos
            .con_socio_vigente()
            .prefetch_related("integrantes")
            .order_by("numero_grupo")
        )

    return render(
        request,
        "core/detalle_seccion.html",
        {
            "seccion": seccion,
            "vista_coordinador": vista_coordinador,
            "equipos": equipos,
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
