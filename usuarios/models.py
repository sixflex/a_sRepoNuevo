from django.db import models
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