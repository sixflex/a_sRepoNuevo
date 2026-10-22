import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0004_seccion_estado_activa"),
        ("cartas", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EnlaceSolicitudCarta",
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
                    "token",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                    ),
                ),
                ("fecha_inicio", models.DateTimeField()),
                (
                    "fecha_expiracion",
                    models.DateTimeField(blank=True, null=True),
                ),
                ("activo", models.BooleanField(default=True)),
                (
                    "creado_por_docente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="enlaces_solicitud_carta_creados",
                        to="academico.docente",
                    ),
                ),
                (
                    "seccion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="enlaces_solicitud_carta",
                        to="academico.seccion",
                    ),
                ),
            ],
        ),
    ]
