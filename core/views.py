from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_required, docente_required

from academico.models import (
    Asignatura,
    Docente,
    PeriodoAcademico,
    Seccion,
)
from .models import CargaPlanificacion, DetalleFilaObservada


@login_required
def inicio(request):
    if es_coordinador(request.user):
        return redirect("core:coordinacion")

    if es_docente(request.user):
        return redirect("core:docente")

    raise PermissionDenied


@coordinador_required
def panel_coordinacion(request):
    total_secciones = Seccion.objects.filter(
        estado__iexact="Activo"
    ).count()

    total_docentes = Docente.objects.filter(
        activo=True
    ).count()

    total_asignaturas = Asignatura.objects.filter(
        activo=True
    ).count()

    total_periodos = PeriodoAcademico.objects.filter(
        estado__iexact="Activo"
    ).count()

    periodo_actual = (
        PeriodoAcademico.objects
        .filter(estado__iexact="Activo")
        .order_by("-anio", "-id")
        .first()
    )

    return render(
        request,
        "core/coordinacion.html",
        {
            "total_secciones": total_secciones,
            "total_docentes": total_docentes,
            "total_asignaturas": total_asignaturas,
            "total_periodos": total_periodos,
            "periodo_actual": periodo_actual,
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
        Seccion.objects
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .prefetch_related("docentes"),
        id=seccion_id,
    )

    if es_coordinador(request.user):
        pass

    elif es_docente(request.user):
        pertenece_al_docente = seccion.docentes.filter(
            usuario=request.user
        ).exists()

        if not pertenece_al_docente:
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


# --- Requerimiento RF-ACA-04: Validación de Planificación Académica ---
@coordinador_required
def validar_planificacion_view(request):
    resumen = None
    errores_filas = []

    if request.method == 'POST':
        enlace = request.POST.get('enlace_planificacion', '')
        unidad = request.POST.get('unidad', 'Departamento de Informática')
        periodo = request.POST.get('periodo', '2026-10')

        # Datos simulados de entrada
        filas_recibidas_raw = [
            {'fila': 1, 'nrc': '12345', 'asignatura': 'Programación Backend'},
            {'fila': 2, 'nrc': '12345', 'asignatura': 'Base de Datos'},         # Duplicado
            {'fila': 3, 'nrc': '67890', 'asignatura': 'Ingeniería de Software'},
            {'fila': 4, 'nrc': '', 'asignatura': ''},                           # Faltan obligatorios
            {'fila': 5, 'nrc': 'ABCDE', 'asignatura': 'Arquitectura Cloud'},    # Formato inválido
        ]

        nrcs_procesados = set()
        filas_aceptadas_list = []

        for item in filas_recibidas_raw:
            fila_num = item['fila']
            nrc = item['nrc'].strip() if item['nrc'] else ''
            asignatura = item['asignatura'].strip() if item['asignatura'] else ''

            causas = []

            # 1. Validación de obligatorios
            if not nrc or not asignatura:
                causas.append("Faltan campos obligatorios (NRC o Asignatura).")

            # 2. Validación de formatos
            if nrc and not nrc.isdigit():
                causas.append(f"El NRC '{nrc}' tiene un formato inválido (debe ser numérico).")

            # 3. Detección de NRC duplicado
            if nrc in nrcs_procesados and nrc != '':
                causas.append(f"NRC '{nrc}' duplicado en la misma entrega.")

            # 4. Separar filas válidas/observadas
            if causas:
                errores_filas.append({
                    'fila': fila_num,
                    'nrc': nrc if nrc else 'N/A',
                    'causa': " | ".join(causas)
                })
            else:
                filas_aceptadas_list.append(item)
                if nrc:
                    nrcs_procesados.add(nrc)

        # 5 y 7. Guardar resumen en la base de datos PostgreSQL
        resumen = CargaPlanificacion.objects.create(
            unidad=unidad,
            periodo=periodo,
            filas_recibidas=len(filas_recibidas_raw),
            filas_aceptadas=len(filas_aceptadas_list),
            filas_observadas=len(errores_filas)
        )

        # 6. Registrar errores por fila en la base de datos
        for err in errores_filas:
            DetalleFilaObservada.objects.create(
                carga=resumen,
                numero_fila=err['fila'],
                nrc=err['nrc'],
                causa_error=err['causa']
            )

    elif request.method == 'GET':
        # Consultar la última carga registrada si es una petición GET
        resumen = CargaPlanificacion.objects.order_by('-id').first()
        if resumen:
            detalles_db = DetalleFilaObservada.objects.filter(carga=resumen)
            for d in detalles_db:
                errores_filas.append({
                    'fila': d.numero_fila,
                    'nrc': d.nrc,
                    'causa': d.causa_error
                })

    historial_cargas = CargaPlanificacion.objects.all().order_by('-id')

    return render(request, 'coordinacion/validar_planificacion.html', {
        'resumen': resumen,
        'errores_filas': errores_filas,
        'historial_cargas': historial_cargas
    })