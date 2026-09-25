from django.conf import settings
from django.db import models


class Archivo(models.Model):
    cargado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archivos_cargados",
    )

    nombre_original = models.CharField(
        max_length=255,
    )

    storage_key = models.CharField(
    max_length=500,
    unique=True,
    )

    mime_type = models.CharField(
        max_length=120,
    )

    tamano_bytes = models.BigIntegerField()

    hash_sha256 = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )

    fecha_carga = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.nombre_original


class RecursoRepositorio(models.Model):
    VISIBILIDAD_CHOICES = [
        ("PUBLICO", "Público"),
        ("PRIVADO", "Privado"),
    ]

    archivo = models.ForeignKey(
        Archivo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recursos_repositorio",
    )

    publicado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recursos_repositorio_publicados",
    )

    titulo = models.CharField(
        max_length=220,
    )

    descripcion = models.TextField(
        null=True,
        blank=True,
    )

    categoria = models.CharField(
        max_length=100,
    )

    url_externa = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    visibilidad = models.CharField(
        max_length=20,
        choices=VISIBILIDAD_CHOICES,
    )

    estado = models.CharField(
        max_length=20,
    )

    fecha_publicacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.titulo