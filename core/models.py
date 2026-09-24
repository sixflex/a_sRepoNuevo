from django.db import models
from usuarios.models import Usuario

class Anio(models.Model):
    numero = models.IntegerField(unique=True) 
    estado = models.BooleanField(default=True)

    def __str__(self):
        return str(self.numero)

class PeriodoAcademico(models.Model):
    nombre = models.CharField(max_length=50) 
    anio = models.ForeignKey(Anio, on_delete=models.CASCADE, related_name='periodos')
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} {self.anio.numero}"

class Docente(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"{self.usuario.first_name} {self.usuario.last_name}"