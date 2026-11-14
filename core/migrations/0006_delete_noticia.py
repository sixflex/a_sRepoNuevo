"""Noticia vive en publico (modelo de datos NOTICIA); sus filas se copiaron en publico 0003."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_initial"),
        ("publico", "0003_pasar_noticias_de_core"),
    ]

    operations = [
        migrations.DeleteModel(name="Noticia"),
    ]
