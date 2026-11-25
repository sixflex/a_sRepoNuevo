

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rutas', '0004_seccionruta_tiene_actividad_cierre'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='rutaactividad',
            name='acepta_evidencias',
        ),
    ]
