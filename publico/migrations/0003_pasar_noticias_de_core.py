"""
Las noticias quedan en una sola tabla, la del modelo de datos (NOTICIA, con
fecha_sincronizacion). Copia las que se hayan creado en core.Noticia, que
luego se elimina (core 0006). No repite URLs ya copiadas.
"""

from django.db import migrations


def copiar(apps, schema_editor):
    Antigua = apps.get_model("core", "Noticia")
    Noticia = apps.get_model("publico", "Noticia")
    existentes = set(Noticia.objects.values_list("url_fuente", flat=True))
    for antigua in Antigua.objects.all():
        if antigua.url_fuente in existentes:
            continue
        Noticia.objects.create(
            titulo=antigua.titulo,
            resumen=antigua.resumen,
            fuente=antigua.fuente or "",
            url_fuente=antigua.url_fuente,
            imagen_url=antigua.imagen_url,
            fecha_publicacion=antigua.fecha_publicacion,
            estado="PUBLICADA" if antigua.estado == "PUBLICADA" else "OCULTA",
        )
        existentes.add(antigua.url_fuente)


class Migration(migrations.Migration):

    dependencies = [
        ("publico", "0002_configuracionportal"),
        ("core", "0005_initial"),
    ]

    operations = [
        migrations.RunPython(copiar, migrations.RunPython.noop),
    ]
