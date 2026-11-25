

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('encuestas', '0003_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='formularioplantilla',
            name='tema_json',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
