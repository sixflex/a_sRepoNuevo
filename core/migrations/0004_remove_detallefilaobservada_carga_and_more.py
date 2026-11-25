

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_cargaplanificacion_fecha_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="detallefilaobservada",
            name="carga",
        ),
        migrations.DeleteModel(
            name="CargaPlanificacion",
        ),
        migrations.DeleteModel(
            name="DetalleFilaObservada",
        ),
    ]
