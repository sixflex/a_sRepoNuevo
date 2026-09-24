import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone

class EnlacePlanificacion(models.Model):
    DESTINATARIO_CHOICES = [
        ('DIRECCION', 'Dirección de Carrera'),
        ('SECRETARIA', 'Secretaría de Estudios'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    destinatario_tipo = models.CharField(max_length=20, choices=DESTINATARIO_CHOICES)
    destinatario_nombre = models.CharField(max_length=150, help_text="Nombre del Director o Secretario")
    destinatario_email = models.EmailField(help_text="Correo institucional")

    sede = models.CharField(max_length=100, default="Sede Santiago")
    campus = models.CharField(max_length=100, default="Campus Providencia")
    carrera = models.CharField(max_length=150, default="Ingeniería Civil Informática")
    periodo = models.CharField(max_length=20, default="2026-2")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_expiracion = models.DateField(help_text="Fecha límite de vigencia")
    activo = models.BooleanField(default=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enlaces_planificacion_creados"
    )

    class Meta:
        verbose_name = "Enlace de Planificación"
        verbose_name_plural = "Enlaces de Planificación"
        ordering = ['-fecha_creacion']

    @property
    def esta_vigente(self):
        return self.activo and self.fecha_expiracion >= timezone.localdate()

    def __str__(self):
        return f"Enlace {self.destinatario_tipo} - {self.carrera} ({'Vigente' if self.esta_vigente else 'Vencido'})"