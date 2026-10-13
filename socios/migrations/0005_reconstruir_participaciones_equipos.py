"""
Reconstruye ParticipacionSocio a partir de los datos heredados.

- Equipo.socio_comunitario -> participación OPERATIVA abierta del equipo.
- HistorialSocioEquipo     -> participaciones cerradas del socio anterior,
  solo cuando el evento indica qué socio había antes.
- Cada evento de HistorialSocioEquipo se copia a AuditoriaCambio (si no
  estaba ya) con socio anterior/nuevo, docente y motivo. La columna y la
  tabla heredadas se eliminan después, en proyectos.0005.

No inventa datos: si no se puede demostrar una fecha de inicio, queda
vacía. Se puede ejecutar más de una vez sin duplicar registros. La
reversa no hace nada.
"""

from django.db import migrations
from django.db.models import Q
from django.utils import timezone

ORIGEN_OPERATIVO = "OPERATIVO"
ENTIDAD_EQUIPO = "Equipo"
ACCION_CAMBIO_SOCIO_EQUIPO = "CAMBIO_SOCIO_EQUIPO"


def _fecha(valor):
    """Fecha local (como timezone.localdate() en el servicio)."""
    if valor is None:
        return None
    if timezone.is_aware(valor):
        valor = timezone.localtime(valor)
    return valor.date()


def _nombre_socio(socio):
    return socio.nombre_organizacion if socio is not None else None


def _contexto(equipo, SeccionCarrera):
    seccion = equipo.seccion
    carreras = list(
        SeccionCarrera.objects
        .filter(seccion_id=seccion.pk)
        .values_list("carrera_id", flat=True)[:2]
    )
    return {
        "proyecto_id": equipo.proyecto_id,
        "seccion_id": seccion.pk,
        "asignatura_id": seccion.asignatura_id,
        "periodo_id": seccion.periodo_id,
        "campus_id": seccion.campus_id,
        "sede_id": seccion.campus.sede_id,
        # Solo si la sección pertenece a una única carrera.
        "carrera_id": carreras[0] if len(carreras) == 1 else None,
    }


def reconstruir_participaciones(apps, schema_editor):
    Equipo = apps.get_model("proyectos", "Equipo")
    HistorialSocioEquipo = apps.get_model("proyectos", "HistorialSocioEquipo")
    ParticipacionSocio = apps.get_model("socios", "ParticipacionSocio")
    SeccionCarrera = apps.get_model("academico", "SeccionCarrera")
    AuditoriaCambio = apps.get_model("auditoria", "AuditoriaCambio")

    equipos_con_historial = HistorialSocioEquipo.objects.values("equipo_id")
    equipos = (
        Equipo.objects
        .filter(Q(socio_comunitario__isnull=False) | Q(pk__in=equipos_con_historial))
        .select_related("seccion", "seccion__campus")
        .order_by("pk")
    )

    for equipo in equipos:
        contexto = _contexto(equipo, SeccionCarrera)
        eventos = list(
            HistorialSocioEquipo.objects
            .filter(equipo_id=equipo.pk)
            .order_by("fecha_cambio", "pk")
        )
        fecha_registro = _fecha(equipo.fecha_registro)

        # Participaciones cerradas: solo si el equipo aún no tiene ninguna,
        # para no duplicar al ejecutar de nuevo.
        if not ParticipacionSocio.objects.filter(equipo_id=equipo.pk).exists():
            for i, evento in enumerate(eventos):
                if evento.socio_anterior_id is None:
                    continue

                if i == 0:
                    fecha_inicio = fecha_registro
                elif eventos[i - 1].socio_nuevo_id == evento.socio_anterior_id:
                    fecha_inicio = _fecha(eventos[i - 1].fecha_cambio)
                else:
                    # La cadena no permite saber desde cuándo estaba.
                    fecha_inicio = None

                fecha_fin = _fecha(evento.fecha_cambio)
                if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
                    fecha_inicio = None

                ParticipacionSocio.objects.create(
                    socio_id=evento.socio_anterior_id,
                    equipo_id=equipo.pk,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    origen=ORIGEN_OPERATIVO,
                    **contexto,
                )

        # Participación vigente según el campo heredado.
        if (
            equipo.socio_comunitario_id
            and not ParticipacionSocio.objects.filter(
                equipo_id=equipo.pk, fecha_fin__isnull=True
            ).exists()
        ):
            ultimo_cambio = [
                e for e in eventos if e.socio_nuevo_id == equipo.socio_comunitario_id
            ]
            fecha_inicio = (
                _fecha(ultimo_cambio[-1].fecha_cambio) if ultimo_cambio else fecha_registro
            )
            ParticipacionSocio.objects.create(
                socio_id=equipo.socio_comunitario_id,
                equipo_id=equipo.pk,
                fecha_inicio=fecha_inicio,
                fecha_fin=None,
                origen=ORIGEN_OPERATIVO,
                **contexto,
            )

    # Copia de los eventos heredados a AUDITORIA_CAMBIO.
    ya_copiados = set()
    for valores in AuditoriaCambio.objects.filter(
        entidad=ENTIDAD_EQUIPO, accion=ACCION_CAMBIO_SOCIO_EQUIPO
    ).values_list("valores_nuevos_json", flat=True):
        if isinstance(valores, dict) and valores.get("historial_socio_equipo_id"):
            ya_copiados.add(valores["historial_socio_equipo_id"])

    eventos = (
        HistorialSocioEquipo.objects
        .exclude(pk__in=ya_copiados)
        .select_related("cambiado_por_docente", "socio_anterior", "socio_nuevo")
        .order_by("pk")
    )
    AuditoriaCambio.objects.bulk_create(
        [
            AuditoriaCambio(
                usuario_id=evento.cambiado_por_docente.usuario_id,
                entidad=ENTIDAD_EQUIPO,
                entidad_id=str(evento.equipo_id),
                accion=ACCION_CAMBIO_SOCIO_EQUIPO,
                valores_anteriores_json={
                    "socio_comunitario_id": evento.socio_anterior_id,
                    "socio_nombre": _nombre_socio(evento.socio_anterior),
                },
                valores_nuevos_json={
                    "socio_comunitario_id": evento.socio_nuevo_id,
                    "socio_nombre": _nombre_socio(evento.socio_nuevo),
                    "motivo": evento.motivo,
                    "docente_id": evento.cambiado_por_docente_id,
                    "docente_nombre": (
                        f"{evento.cambiado_por_docente.nombres} "
                        f"{evento.cambiado_por_docente.apellidos}"
                    ).strip(),
                    "historial_socio_equipo_id": evento.pk,
                    "origen": "migracion HistorialSocioEquipo",
                },
                fecha=evento.fecha_cambio,
            )
            for evento in eventos
        ]
    )


class Migration(migrations.Migration):

    dependencies = [
        ("socios", "0004_participacionsocio_equipo_opcional_restricciones"),
        ("proyectos", "0004_historialsocioequipo"),
        ("academico", "0004_seccion_estado_activa"),
        ("auditoria", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(reconstruir_participaciones, migrations.RunPython.noop),
    ]
