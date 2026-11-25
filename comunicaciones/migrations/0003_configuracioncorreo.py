

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("comunicaciones", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionCorreo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "remitente_nombre",
                    models.CharField(default="Coordinación A+S", max_length=120),
                ),
                ("remitente_correo", models.EmailField(max_length=254)),
                ("responder_a", models.EmailField(blank=True, max_length=254)),
                (
                    "proveedor",
                    models.CharField(
                        choices=[
                            ("MICROSOFT", "Microsoft 365 / Outlook (cuentas de la U)"),
                            ("GMAIL", "Gmail"),
                            ("OTRO", "Otro servidor"),
                        ],
                        default="MICROSOFT",
                        max_length=20,
                    ),
                ),
                ("servidor_smtp", models.CharField(max_length=120)),
                ("puerto", models.PositiveIntegerField(default=587)),
                ("usar_tls", models.BooleanField(default=True)),
                ("clave_cifrada", models.TextField(blank=True)),
                ("activo", models.BooleanField(default=False)),
                ("fecha_verificacion", models.DateTimeField(blank=True, null=True)),
                ("fecha_modificacion", models.DateTimeField(auto_now=True)),
                (
                    "modificado_por_usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "configuración de correo",
                "verbose_name_plural": "configuración de correo",
            },
        ),
    ]
