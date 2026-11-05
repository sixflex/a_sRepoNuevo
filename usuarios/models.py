from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractUser


class Rol(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    rol = models.ForeignKey(
        Rol,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    entra_oid = models.CharField(
        max_length=80,
        unique=True,
        null=True,
        blank=True,
    )

    correo_institucional = models.EmailField(
        max_length=254,
        unique=True,
        null=True,
        blank=True,
    )

    activo = models.BooleanField(default=True)

    fecha_ultimo_acceso = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        nombre = f"{self.first_name} {self.last_name}".strip()
        correo = self.correo_institucional or self.email

        return f"{nombre} - {correo}"

class IdentidadInstitucional(models.Model):
    """
    Una cuenta Microsoft con la que una persona puede entrar al portal.

    La universidad tiene dos tipos de cuenta (@uautonoma.cl y
    @cloud.uautonoma.cl) y algunas personas tienen ambas. Cada cuenta es una
    identidad; todas las de una persona apuntan al mismo Usuario. La principal
    se copia en Usuario.entra_oid y Usuario.correo_institucional.
    """

    INICIAL = "INICIAL"
    AUTOMATICO_RUT = "AUTOMATICO_RUT"
    CONFIRMADO_USUARIO = "CONFIRMADO_USUARIO"
    MANUAL_COORDINADOR = "MANUAL_COORDINADOR"

    ORIGENES_VINCULO = [
        (INICIAL, "Primera cuenta con la que entró"),
        (AUTOMATICO_RUT, "Vinculada automáticamente por RUT"),
        (CONFIRMADO_USUARIO, "Vinculada por la persona"),
        (MANUAL_COORDINADOR, "Vinculada por Coordinación"),
    ]

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="identidades",
    )

    tenant_id = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )

    entra_oid = models.CharField(max_length=80)

    # Siempre en minúsculas.
    correo = models.EmailField(max_length=254, unique=True)

    es_principal = models.BooleanField(default=False)

    origen_vinculo = models.CharField(
        max_length=30,
        choices=ORIGENES_VINCULO,
        default=INICIAL,
    )

    fecha_vinculacion = models.DateTimeField(default=timezone.now)

    fecha_ultimo_acceso = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "identidad institucional"
        verbose_name_plural = "identidades institucionales"
        ordering = ["-es_principal", "correo"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "entra_oid"],
                name="identidad_tenant_oid_unica",
            ),
            models.UniqueConstraint(
                fields=["usuario"],
                condition=models.Q(es_principal=True),
                name="identidad_una_principal_por_usuario",
            ),
        ]

    @property
    def dominio(self):
        return self.correo.rsplit("@", 1)[-1]

    def save(self, *args, **kwargs):
        self.correo = (self.correo or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.correo
