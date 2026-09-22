from django.db import models


class Campus(models.Model):
    nombre = models.CharField(max_length=100)
    direccion = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre


class Sede(models.Model):
    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name='sedes'
    )
    nombre = models.CharField(max_length=100)
    ciudad = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nombre} - {self.ciudad}"



class Facultad(models.Model):
    nombre = models.CharField(max_length=150)

    def __str__(self):
        return self.nombre


class Carrera(models.Model):
    nombre = models.CharField(max_length=150)

    facultad = models.ForeignKey(
        Facultad,
        on_delete=models.CASCADE,
        related_name='carreras',
        null=True,
        blank=True
    )

    def __str__(self):
        return self.nombre



class Asignatura(models.Model):
    nombre = models.CharField(max_length=150)
    carrera = models.ForeignKey(
        Carrera,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return self.nombre


class Docente(models.Model):
    nombre = models.CharField(max_length=150)
    correo = models.EmailField()

    def __str__(self):
        return self.nombre


class Periodo(models.Model):
    anio = models.IntegerField()
    tipo = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.anio} - {self.tipo}"


class Seccion(models.Model):
    nrc = models.CharField(max_length=20, unique=True)
    asignatura = models.ForeignKey(
        Asignatura,
        on_delete=models.CASCADE
    )
    docente = models.ForeignKey(
        Docente,
        on_delete=models.CASCADE
    )
    periodo = models.ForeignKey(
        Periodo,
        on_delete=models.CASCADE
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{self.nrc} - {self.asignatura}"