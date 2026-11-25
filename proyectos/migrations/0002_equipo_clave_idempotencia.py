

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proyectos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipo',
            name='clave_idempotencia',
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
    ]
