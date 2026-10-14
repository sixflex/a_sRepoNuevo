from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q

from .models import RutaActividad, RutaVersion, SeccionActividad, SeccionRuta


@transaction.atomic
def asignar_ruta_a_seccion(seccion, ruta_version):
    seccion_ruta, creada = SeccionRuta.objects.get_or_create(
        seccion=seccion,
        defaults={
            "ruta_version": ruta_version,
            "estado": "EN_PROGRESO",
            "porcentaje_final": Decimal("0.00"),
        },
    )

    if not creada and seccion_ruta.ruta_version_id != ruta_version.id:
        raise ValueError(
            "La sección ya tiene asignada una versión diferente de la Ruta A+S."
        )

    actividades = RutaActividad.objects.filter(
        ruta_version=ruta_version
    ).order_by("orden")

    for actividad in actividades:
        SeccionActividad.objects.get_or_create(
            seccion_ruta=seccion_ruta,
            ruta_actividad=actividad,
            defaults={
                "estado": "PENDIENTE",
            },
        )

    return seccion_ruta


def obtener_version_ruta_vigente():
    return (
        RutaVersion.objects
        .filter(
            plantilla__nombre="Ruta del Docente A+S",
            plantilla__activo=True,
            estado="ACTIVA",
        )
        .order_by("-numero_version")
        .first()
    )


def asignar_ruta_as_si_corresponde(seccion):
    es_as = seccion.seccion_carreras.filter(
        declaracion_as=True
    ).exists()

    if not es_as:
        return None

    ruta_version = obtener_version_ruta_vigente()

    if ruta_version is None:
        return None

    return asignar_ruta_a_seccion(
        seccion,
        ruta_version,
    )


def con_avance(rutas):
    """
    Anota en cada SeccionRuta sus actividades obligatorias totales y
    completadas (RF-RUT-03: las opcionales no cuentan). Es el mismo cálculo
    del inicio docente; el panel del coordinador lo usa por carrera.
    """
    return rutas.annotate(
        total_obligatorias=Count(
            "actividades",
            filter=Q(actividades__ruta_actividad__es_obligatoria=True),
        ),
        completadas_obligatorias=Count(
            "actividades",
            filter=Q(
                actividades__ruta_actividad__es_obligatoria=True,
                actividades__completada_por_docente__isnull=False,
            ),
        ),
    )


def porcentaje_avance(completadas, total):
    """Porcentaje entero de obligatorias completadas (0 si no hay obligatorias)."""
    return round(completadas * 100 / total) if total else 0
