from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from academico.models import (
    Asignatura,
    Carrera,
    Docente,
    Seccion,
    SeccionCarrera,
    SeccionDocente,
)

from .models import (
    FilaPlanificacion,
    PlanificacionError,
)

ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_ACEPTADA = "ACEPTADA"
ESTADO_OBSERVADA = "OBSERVADA"

def _texto(valor):
    return (valor or "").strip()

def _registrar_error(fila, campo, codigo, mensaje):
    PlanificacionError.objects.create(
        fila=fila,
        campo=campo,
        codigo=codigo,
        mensaje=mensaje,
    )

def _resolver_carrera(fila):
    nombre = _texto(fila.carrera_texto)

    if not nombre:
        _registrar_error(
            fila,
            "carrera",
            "CAMPO_OBLIGATORIO",
            "Debe indicar una carrera.",
        )
        return None

    carrera = (
        Carrera.objects
        .filter(nombre__iexact=nombre, activo=True)
        .first()
    )

    if carrera is None:
        _registrar_error(
            fila,
            "carrera",
            "CARRERA_NO_ENCONTRADA",
            f'No existe una carrera activa con el nombre "{nombre}".',
        )

    return carrera

def _resolver_asignatura(fila, carrera):
    nombre = _texto(fila.asignatura_texto)

    if not nombre:
        _registrar_error(
            fila,
            "asignatura",
            "CAMPO_OBLIGATORIO",
            "Debe indicar una asignatura.",
        )
        return None

    queryset = Asignatura.objects.filter(
        activo=True,
    ).filter(
        Q(nombre__iexact=nombre)
        | Q(codigo__iexact=nombre)
    )

    if carrera is not None:
        queryset = queryset.filter(
            carreras=carrera
        )

    asignatura = queryset.distinct().first()

    if asignatura is None:
        _registrar_error(
            fila,
            "asignatura",
            "ASIGNATURA_NO_ENCONTRADA",
            (
                f'No se encontró la asignatura "{nombre}" '
                "asociada a la carrera indicada."
            ),
        )

    return asignatura

def _validar_campos_basicos(fila):
    valido = True

    if not _texto(fila.nrc):
        _registrar_error(
            fila,
            "nrc",
            "CAMPO_OBLIGATORIO",
            "Debe indicar el NRC.",
        )
        valido = False

    if not _texto(fila.seccion):
        _registrar_error(
            fila,
            "seccion",
            "CAMPO_OBLIGATORIO",
            "Debe indicar la sección.",
        )
        valido = False

    if (
        fila.estudiantes_planificados is not None
        and fila.estudiantes_planificados < 0
    ):
        _registrar_error(
            fila,
            "estudiantes_planificados",
            "VALOR_INVALIDO",
            "La cantidad de estudiantes no puede ser negativa.",
        )
        valido = False

    return valido

def _validar_nrc(fila):
    periodo = fila.planificacion.enlace.periodo
    nrc = _texto(fila.nrc)

    if not nrc:
        return False

    existente = Seccion.objects.filter(
        periodo=periodo,
        nrc__iexact=nrc,
    ).first()

    if existente is not None:
        _registrar_error(
            fila,
            "nrc",
            "NRC_DUPLICADO",
            (
                f'El NRC "{nrc}" ya se encuentra registrado '
                f"para el período {periodo.nombre}."
            ),
        )
        return False

    return True

def _resolver_docente(docente_fila):

    rut = _texto(docente_fila.rut)
    correo = _texto(docente_fila.correo)

    docente = None

    if rut:
        docente = Docente.objects.filter(
            rut__iexact=rut
        ).first()

    if docente is None and correo:
        docente = Docente.objects.filter(
            correo_institucional__iexact=correo
        ).first()

    return docente

def _validar_docentes(fila):
    docentes_fila = list(fila.docentes.all())

    if not docentes_fila:
        _registrar_error(
            fila,
            "docente",
            "DOCENTE_OBLIGATORIO",
            "La fila debe contener al menos un docente.",
        )
        return False

    valido = True

    for docente_fila in docentes_fila:
        docente = _resolver_docente(docente_fila)

        if docente is None:
            _registrar_error(
                fila,
                "docente",
                "DOCENTE_NO_ENCONTRADO",
                (
                    "No fue posible relacionar al docente "
                    f'"{docente_fila.nombre or "Sin nombre"}" '
                    "con un docente registrado."
                ),
            )
            valido = False
            continue

        docente_fila.docente_resuelto = docente
        docente_fila.save(
            update_fields=["docente_resuelto"]
        )

    return valido


def validar_fila(fila):
    fila.errores.all().delete()

    fila.campus_resuelto = None
    fila.carrera_resuelta = None
    fila.asignatura_resuelta = None
    fila.seccion_resultante = None

    fila.docentes.update(docente_resuelto=None)

    valido = _validar_campos_basicos(fila)

    enlace = fila.planificacion.enlace

    campus = enlace.campus

    if campus is None or not campus.activo:
        _registrar_error(
            fila,
            "campus",
            "CAMPUS_INVALIDO",
            "El campus asociado al enlace no se encuentra activo.",
        )
        valido = False
    else:
        fila.campus_resuelto = campus

    carrera = _resolver_carrera(fila)

    if carrera is None:
        valido = False
    else:
        fila.carrera_resuelta = carrera

    asignatura = _resolver_asignatura(
        fila,
        carrera,
    )

    if asignatura is None:
        valido = False
    else:
        fila.asignatura_resuelta = asignatura

    if not _validar_nrc(fila):
        valido = False

    if not _validar_docentes(fila):
        valido = False

    fila.estado_validacion = (
        ESTADO_ACEPTADA
        if valido
        else ESTADO_OBSERVADA
    )

    fila.save(
        update_fields=[
            "campus_resuelto",
            "carrera_resuelta",
            "asignatura_resuelta",
            "seccion_resultante",
            "estado_validacion",
        ]
    )

    return valido

def consolidar_fila(fila):
    if fila.estado_validacion != ESTADO_ACEPTADA:
        return None

    planificacion = fila.planificacion
    enlace = planificacion.enlace

    seccion = Seccion.objects.create(
        periodo=enlace.periodo,
        campus=fila.campus_resuelto,
        asignatura=fila.asignatura_resuelta,
        nrc=_texto(fila.nrc),
        seccion=_texto(fila.seccion),
        jornada=_texto(fila.jornada) or None,
        horario=_texto(fila.horario) or None,
        estado="Activo",
        fecha_consolidacion=timezone.now(),
    )

    SeccionCarrera.objects.create(
        seccion=seccion,
        carrera=fila.carrera_resuelta,
        nivel=_texto(fila.nivel) or None,
        declaracion_as=fila.declaracion_as,
        estudiantes_planificados=fila.estudiantes_planificados,
    )

    for docente_fila in fila.docentes.select_related(
        "docente_resuelto"
    ):
        if docente_fila.docente_resuelto is None:
            continue

        SeccionDocente.objects.get_or_create(
            seccion=seccion,
            docente=docente_fila.docente_resuelto,
            defaults={
                "tipo_contrato": (
                    _texto(docente_fila.tipo_contrato)
                    or None
                ),
                "capacitado_as": docente_fila.capacitado_as,
            },
        )

    fila.seccion_resultante = seccion
    fila.save(
        update_fields=["seccion_resultante"]
    )

    return seccion

@transaction.atomic
def validar_y_consolidar_planificacion(planificacion):
    filas = planificacion.filas.all()

    for fila in filas:
        es_valida = validar_fila(fila)

        if not es_valida:
            continue

        try:
            with transaction.atomic():
                consolidar_fila(fila)

        except IntegrityError:
            fila.estado_validacion = ESTADO_OBSERVADA
            fila.seccion_resultante = None

            fila.save(
                update_fields=[
                    "estado_validacion",
                    "seccion_resultante",
                ]
            )

            _registrar_error(
                fila,
                "general",
                "ERROR_INTEGRIDAD",
                (
                    "No fue posible consolidar la fila debido "
                    "a un conflicto con los datos académicos existentes."
                ),
            )
    planificacion.filas_recibidas = planificacion.filas.count()
    planificacion.filas_aceptadas = planificacion.filas.filter(estado_validacion=ESTADO_ACEPTADA).count()
    planificacion.filas_observadas = planificacion.filas.filter(estado_validacion=ESTADO_OBSERVADA).count()
    planificacion.save(update_fields=["filas_recibidas","filas_aceptadas","filas_observadas",])

    return planificacion