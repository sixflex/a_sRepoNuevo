from django.db import models
from django.utils import timezone

# Core no define modelos propios previamente: la planificación de la Dirección de
# Carrera vive en la app planificacion (RF-ACA-02..04) y los datos
# académicos en academico.

class Noticia(models.Model):
    ESTADO_CHOICES = [
        ("PUBLICADA", "Publicada"),
        ("BORRADOR", "Borrador"),
    ]

    titulo = models.CharField("Título", max_length=255)
    resumen = models.TextField("Resumen", blank=True)
    fuente = models.CharField("Fuente", max_length=150, blank=True)
    url_fuente = models.URLField("URL Fuente", max_length=500, unique=True, help_text="Enlace único de la noticia original.")
    imagen_url = models.URLField("URL Imagen", max_length=500, blank=True, null=True)
    fecha_publicacion = models.DateTimeField("Fecha de publicación", default=timezone.now)
    estado = models.CharField("Estado", max_length=20, choices=ESTADO_CHOICES, default="PUBLICADA")

    class Meta:
        verbose_name = "Noticia"
        verbose_name_plural = "Noticias"
        ordering = ["-fecha_publicacion"]

    def __str__(self):
        return self.titulo