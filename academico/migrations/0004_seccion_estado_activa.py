"""
Seccion.estado usa Planificada / Activa / Finalizada. La consolidación de
planificaciones y los datos de prueba guardaban "Activo": pasa a "Activa".
Hacia atrás no hace nada ("Activa" ya era un valor válido antes).
"""

from django.db import migrations


def pasar_a_activa(apps, schema_editor):
    Seccion = apps.get_model("academico", "Seccion")
    Seccion.objects.filter(estado__iexact="Activo").update(estado="Activa")


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0003_periodo_tipo_por_duracion"),
    ]

    operations = [
        migrations.RunPython(pasar_a_activa, migrations.RunPython.noop),
    ]
