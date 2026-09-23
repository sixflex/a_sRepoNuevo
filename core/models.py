from django.db import models

class CargaPlanificacion(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    unidad = models.CharField(max_length=100)
    periodo = models.CharField(max_length=20)
    enlace_origen = models.URLField(max_length=500)
    filas_recibidas = models.IntegerField(default=0)
    filas_aceptadas = models.IntegerField(default=0)
    filas_observadas = models.IntegerField(default=0)

    def __str__(self):
        return f"Carga {self.unidad} - {self.periodo} ({self.fecha.strftime('%d/%m/%Y')})"

class DetalleFilaObservada(models.Model):
    carga = models.ForeignKey(CargaPlanificacion, related_name='observaciones', on_delete=models.CASCADE)
    numero_fila = models.IntegerField()
    nrc = models.CharField(max_length=20, blank=True, null=True)
    causa_error = models.TextField()

    def __str__(self):
        return f"Fila {self.numero_fila}: {self.causa_error}"