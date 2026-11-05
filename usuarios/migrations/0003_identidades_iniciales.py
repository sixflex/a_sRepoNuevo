"""Una identidad principal (INICIAL) para cada usuario que ya existía con correo."""
from django.db import migrations


def crear_identidades(apps, schema_editor):
    from usuarios.services import crear_identidades_iniciales

    crear_identidades_iniciales(
        modelo_usuario=apps.get_model("usuarios", "Usuario"),
        modelo_identidad=apps.get_model("usuarios", "IdentidadInstitucional"),
    )


def borrar_identidades(apps, schema_editor):
    apps.get_model("usuarios", "IdentidadInstitucional").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0002_identidad_institucional"),
    ]

    operations = [
        migrations.RunPython(crear_identidades, borrar_identidades),
    ]
