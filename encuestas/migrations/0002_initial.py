

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("encuestas", "0001_initial"),
        ("socios", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="enlaceformulario",
            name="convocatoria",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="enlaces_formulario",
                to="socios.convocatoria",
            ),
        ),
    ]
