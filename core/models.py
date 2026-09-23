from django.db import models
from usuarios.models import Usuario

class Sede(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    ubicacion = models.CharField(max_length=255, blank=True, null=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class Campus(models.Model):
    nombre = models.CharField(max_length=100)
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='campus')
    estado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.sede.nombre})"

class Facultad(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class Carrera(models.Model):
    nombre = models.CharField(max_length=150)
    facultad = models.ForeignKey(Facultad, on_delete=models.CASCADE, related_name='carreras')
    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

class Asignatura(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE, related_name='asignaturas')
    estado = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

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

class Seccion(models.Model):
    nrc = models.CharField(max_length=50, unique=True)
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    docente = models.ForeignKey(Docente, on_delete=models.CASCADE)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE)
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE)
    periodo = models.ForeignKey(PeriodoAcademico, on_delete=models.CASCADE)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return f"NRC: {self.nrc} - {self.asignatura.nombre}"