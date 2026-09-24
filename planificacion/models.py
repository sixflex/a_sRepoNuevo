import uuid
from django.db import models
from academico.models import Carrera, Campus, Asignatura, Docente

class PlanificacionAS(models.Model):
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('FINAL', 'Versión Final'),
    ]

    # Identificación
    carrera = models.ForeignKey(
        Carrera, 
        on_delete=models.CASCADE, 
        related_name='planificaciones_as'
    )
    token_acceso = models.UUIDField(default=uuid.uuid4, editable=False)
    estado_registro = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='BORRADOR')

    # Campos RF-ACA-03
    declaracion_as = models.BooleanField(default=False, verbose_name="Declaración A+S")
    nrc = models.CharField(max_length=50, verbose_name="NRC")
    campus = models.ForeignKey(Campus, on_delete=models.SET_NULL, null=True, blank=True)
    seccion = models.CharField(max_length=20, verbose_name="Sección")
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    nivel = models.CharField(max_length=20)
    horario = models.CharField(max_length=100)
    estudiantes_planificados = models.IntegerField(verbose_name="Estudiantes Planificados")
    docente = models.ForeignKey(Docente, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.nrc} - {self.asignatura.nombre} ({self.estado_registro})"
    class Meta:
        verbose_name = "Planificación A+S"
        verbose_name_plural = "Planificaciones A+S"

    def __str__(self):
        return f"{self.nrc} - {self.asignatura.nombre} ({self.get_estado_registro_display()})"