from django.conf import settings
from django.db import models


class AuditoriaCambio(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cambios_auditoria",
    )

    actor_externo = models.CharField(
        max_length=254,
        null=True,
        blank=True,
    )

    entidad = models.CharField(max_length=120)

    entidad_id = models.CharField(max_length=80)

    accion = models.CharField(max_length=60)

    valores_anteriores_json = models.JSONField(
        null=True,
        blank=True,
    )

    valores_nuevos_json = models.JSONField(
        null=True,
        blank=True,
    )

    fecha = models.DateTimeField()

    ip = models.CharField(
        max_length=45,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.entidad} - {self.accion} - {self.fecha}"