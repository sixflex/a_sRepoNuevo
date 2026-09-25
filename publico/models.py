from django.db import models


class Noticia(models.Model):
    titulo = models.CharField(max_length=255)

    resumen = models.TextField(
        null=True,
        blank=True,
    )

    fuente = models.CharField(max_length=180)

    url_fuente = models.CharField(max_length=500)

    imagen_url = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    fecha_publicacion = models.DateTimeField()

    fecha_sincronizacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    estado = models.CharField(max_length=20)

    def __str__(self):
        return self.titulo