

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archivos', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='archivo',
            name='extension',
            field=models.CharField(default=' ', max_length=20),
            preserve_default=False,
        ),
    ]
