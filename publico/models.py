from django.conf import settings
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

class ConfiguracionPortal(models.Model):
    """
    Qué muestra el portal público (RF-PUB-01: "lo que el Coordinador haya
    definido como públicos"). Es una sola fila; las opciones se guardan en
    JSON según publico/portal.py, así agregar una cifra o un dato nuevo no
    necesita otra migración. Lo que no esté guardado se muestra.
    """

    opciones_json = models.JSONField(default=dict, blank=True)

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    fecha_actualizacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Configuración del portal público"
        verbose_name_plural = "Configuración del portal público"

    def __str__(self):
        return "Configuración del portal público"
