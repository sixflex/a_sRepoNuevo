

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0002_equipo_clave_idempotencia'),
        ('socios', '0003_historialestadosocio'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipo',
            name='socio_comunitario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='equipos', to='socios.sociocomunitario'),
        ),
    ]
