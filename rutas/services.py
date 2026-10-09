from decimal import Decimal

from django.db import transaction

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