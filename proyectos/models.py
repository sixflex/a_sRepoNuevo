from django.db import models
from django.contrib.auth.models import User


class Seccion(models.Model):
    nombre = models.CharField(max_length=100)
    nrc = models.CharField(max_length=20, unique=True)

    docente = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="secciones_asignadas",
    )

    def __str__(self):
        return f"{self.nombre} - NRC {self.nrc}"