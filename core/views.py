from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_required, docente_required

from academico.constantes import SECCION_ACTIVA
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
            # El inicio del docente es el resumen de sus Rutas A+S;
            # "Mis secciones" (core:docente) queda como opción del menú.
            return redirect("core:inicio_docente")

    return render(request, "core/inicio.html")


@coordinador_required
def panel_coordinacion(request):
    from cartas.models import SolicitudCarta
    from planificacion.models import Planificacion
    from socios.models import PostulacionSocio

    total_secciones = Seccion.objects.filter(
        estado=SECCION_ACTIVA
    ).count()

    total_docentes = Docente.objects.filter(
        activo=True
    ).count()

    total_asignaturas = Asignatura.objects.filter(
        activo=True
    ).count()

    total_periodos = PeriodoAcademico.objects.filter(
        estado="Activo"
    ).count()

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

    return render(
        request,
        "core/coordinacion.html",
        {
            "total_secciones": total_secciones,
            "total_docentes": total_docentes,
            "total_asignaturas": total_asignaturas,
            "total_periodos": total_periodos,
            "periodo_actual": periodo_actual,
            "pendientes": pendientes,
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
    secciones_docente = (
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

    periodos = (
        PeriodoAcademico.objects
        .filter(secciones__in=secciones_docente)
        .distinct()
        .order_by("-anio", "-id")
    )

    anios = (
        periodos
        .order_by("-anio")
        .values_list("anio", flat=True)
        .distinct()
    )

    anio_seleccionado = request.GET.get("anio", "").strip()
    periodo_seleccionado = request.GET.get("periodo", "").strip()

    secciones = secciones_docente

    if anio_seleccionado:
        if anio_seleccionado.isdigit():
            secciones = secciones.filter(
                periodo__anio=int(anio_seleccionado)
            )
        else:
            secciones = secciones.none()

    if periodo_seleccionado:
        if periodo_seleccionado.isdigit():
            secciones = secciones.filter(
                periodo_id=int(periodo_seleccionado)
            )
        else:
            secciones = secciones.none()

    if anio_seleccionado:
        periodos = periodos.filter(
            anio=anio_seleccionado
        ) if anio_seleccionado.isdigit() else periodos.none()

    secciones = secciones.order_by(
        "-periodo__anio",
        "-periodo_id",
        "asignatura__nombre",
    )

    return render(
        request,
        "core/docente.html",
        {
            "secciones": secciones,
            "anios": anios,
            "periodos": periodos,
            "anio_seleccionado": anio_seleccionado,
            "periodo_seleccionado": periodo_seleccionado,
            "filtros_activos": bool(
                anio_seleccionado or periodo_seleccionado
            ),
        },
    )


@docente_required
def inicio_docente(request):
    from django.db.models import Count, Q
    from rutas.models import SeccionRuta

    secciones = (
        Seccion.objects
        .filter(docentes__usuario=request.user)
        .distinct()
    )

    rutas = list(
        SeccionRuta.objects
        .filter(seccion__in=secciones)
        .select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
        )
        .annotate(
            total_obligatorias=Count(
                "actividades",
                filter=Q(
                    actividades__ruta_actividad__es_obligatoria=True
                ),
            ),
            completadas_obligatorias=Count(
                "actividades",
                filter=Q(
                    actividades__ruta_actividad__es_obligatoria=True,
                    actividades__completada_por_docente__isnull=False,
                ),
            ),
        )
        .order_by(
            "-seccion__periodo__anio",
            "seccion__asignatura__nombre",
        )
    )

    total_obligatorias = 0
    total_completadas = 0
    total_pendientes = 0

    for ruta in rutas:
        ruta.pendientes_obligatorias = (
            ruta.total_obligatorias
            - ruta.completadas_obligatorias
        )

        ruta.avance_calculado = (
            round(
                ruta.completadas_obligatorias
                * 100
                / ruta.total_obligatorias
            )
            if ruta.total_obligatorias
            else 0
        )

        total_obligatorias += ruta.total_obligatorias
        total_completadas += ruta.completadas_obligatorias
        total_pendientes += ruta.pendientes_obligatorias

    avance_general = (
        round(total_completadas * 100 / total_obligatorias)
        if total_obligatorias
        else 0
    )

    return render(
        request,
        "core/inicio_docente.html",
        {
            "total_secciones": secciones.count(),
            "rutas_completadas": sum(
                ruta.estado == "COMPLETADA"
                for ruta in rutas
            ),
            "total_pendientes": total_pendientes,
            "avance_general": avance_general,
            "rutas": rutas,
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
