from django.db import models
from django.utils import timezone

class CargaPlanificacion(models.Model):
    unidad = models.CharField(max_length=255, default='Departamento de Informática')
    periodo = models.CharField(max_length=50, default='2026-10')
    filas_recibidas = models.IntegerField(default=0)
    filas_aceptadas = models.IntegerField(default=0)
    filas_observadas = models.IntegerField(default=0)
    fecha = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Carga #{self.id} - {self.unidad} ({self.periodo})"

class DetalleFilaObservada(models.Model):
    carga = models.ForeignKey(
        CargaPlanificacion, 
        on_delete=models.CASCADE, 
        related_name='detalles',
        null=True, 
        blank=True
    )
    numero_fila = models.IntegerField(default=0)
    nrc = models.CharField(max_length=50, blank=True, default='')
    causa_error = models.TextField(default='')

    def __str__(self):
        return f"Fila {self.numero_fila}"