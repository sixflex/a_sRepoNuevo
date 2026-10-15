from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch
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

def obtener_recordatorios_ruta(secciones):
    from socios.models import InvitacionCierre

    seccion_ids = [seccion.id for seccion in secciones]

    if not seccion_ids:
        return {}

    seccion_rutas = (
        SeccionRuta.objects
        .filter(seccion_id__in=seccion_ids)
        .exclude(estado="COMPLETADA")
        .prefetch_related(
            Prefetch(
                "actividades",
                queryset=(
                    SeccionActividad.objects
                    .filter(completada_por_docente__isnull=True)
                    .select_related("ruta_actividad")
                    .order_by("ruta_actividad__orden")
                ),
                to_attr="actividades_pendientes",
            ),
            Prefetch(
                "invitaciones_cierre",
                queryset=InvitacionCierre.objects.select_related("socio"),
                to_attr="invitaciones_cargadas",
            ),
        )
    )

    recordatorios = {}

    for seccion_ruta in seccion_rutas:
        pendientes = seccion_ruta.actividades_pendientes
        invitaciones = seccion_ruta.invitaciones_cargadas

        hay_actividad_cierre = (
            seccion_ruta.tiene_actividad_cierre is True
            or len(invitaciones) > 0
        )

        recordatorios[seccion_ruta.seccion_id] = {
            "seccion_ruta": seccion_ruta,
            "pendientes": pendientes,
            "total_pendientes": len(pendientes),
            "obligatorias_pendientes": sum(
                1
                for actividad in pendientes
                if actividad.ruta_actividad.es_obligatoria
            ),
            "hay_actividad_cierre": hay_actividad_cierre,
            "invitaciones": invitaciones,
            "falta_invitar_socio": (
                hay_actividad_cierre and len(invitaciones) == 0
            ),
        }

    return recordatorios