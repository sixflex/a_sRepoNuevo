"""
Equipo deja de guardar su socio (modelo de BD aprobado: EQUIPO no tiene FK
a socio y no existe HistorialSocioEquipo).

Depende de socios.0005, que antes de este paso reconstruye ParticipacionSocio
desde Equipo.socio_comunitario e HistorialSocioEquipo y copia cada cambio a
AUDITORIA_CAMBIO. Desde aquí el socio vigente sale de la participación
abierta y el historial de cambios, de la auditoría.

Reversa: vuelve a crear la columna y la tabla, y repone
Equipo.socio_comunitario desde la participación abierta. HistorialSocioEquipo
vuelve vacío: los cambios siguen completos en AUDITORIA_CAMBIO.
"""

from django.db import migrations


def reponer_socio_comunitario(apps, schema_editor):
    Equipo = apps.get_model("proyectos", "Equipo")
    ParticipacionSocio = apps.get_model("socios", "ParticipacionSocio")

    abiertas = (
        ParticipacionSocio.objects
        .filter(equipo__isnull=False, fecha_fin__isnull=True)
        .values_list("equipo_id", "socio_id")
    )
    for equipo_id, socio_id in abiertas:
        Equipo.objects.filter(pk=equipo_id).update(socio_comunitario_id=socio_id)


class Migration(migrations.Migration):

    dependencies = [
        ("proyectos", "0004_historialsocioequipo"),
        ("socios", "0005_reconstruir_participaciones_equipos"),
    ]

    operations = [
        # Solo actúa al revertir (las operaciones se deshacen en orden
        # inverso, así que corre después de volver a crear la columna).
        migrations.RunPython(migrations.RunPython.noop, reponer_socio_comunitario),
        migrations.RemoveField(
            model_name="equipo",
            name="socio_comunitario",
        ),
        migrations.DeleteModel(
            name="HistorialSocioEquipo",
        ),
    ]
