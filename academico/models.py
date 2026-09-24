from django.conf import settings
from django.db import models


class Sede(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    ciudad = models.CharField(max_length=120, null=True, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Campus(models.Model):
    sede = models.ForeignKey(
        Sede,
        on_delete=models.CASCADE,
        related_name="campus"
    )
    nombre = models.CharField(max_length=120)
    direccion = models.CharField(max_length=255, null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sede", "nombre"],
                name="unique_campus_sede_nombre"
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.sede.nombre}"


class Facultad(models.Model):
    codigo = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )
    nombre = models.CharField(max_length=160)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Carrera(models.Model):
    facultad = models.ForeignKey(
        Facultad,
        on_delete=models.CASCADE,
        related_name="carreras"
    )
    codigo = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )
    nombre = models.CharField(max_length=180)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class Asignatura(models.Model):
    codigo = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True
    )
    nombre = models.CharField(max_length=180)
    activo = models.BooleanField(default=True)

    carreras = models.ManyToManyField(
        Carrera,
        through="AsignaturaCarrera",
        related_name="asignaturas"
    )

    def __str__(self):
        if self.codigo:
            return f"{self.codigo} - {self.nombre}"
        return self.nombre


class AsignaturaCarrera(models.Model):
    asignatura = models.ForeignKey(
        Asignatura,
        on_delete=models.CASCADE,
        related_name="asignatura_carreras"
    )
    carrera = models.ForeignKey(
        Carrera,
        on_delete=models.CASCADE,
        related_name="asignatura_carreras"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["asignatura", "carrera"],
                name="unique_asignatura_carrera"
            )
        ]

    def __str__(self):
        return f"{self.asignatura} - {self.carrera}"


class Docente(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfil_docente"
    )
    rut = models.CharField(max_length=12, unique=True)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    correo_institucional = models.EmailField(unique=True)
    telefono = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class PeriodoAcademico(models.Model):
    anio = models.SmallIntegerField()
    tipo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=80)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["anio", "tipo", "nombre"],
                name="unique_periodo_academico"
            )
        ]

    def __str__(self):
        return self.nombre


class Seccion(models.Model):
    periodo = models.ForeignKey(
        PeriodoAcademico,
        on_delete=models.CASCADE,
        related_name="secciones"
    )
    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name="secciones"
    )
    asignatura = models.ForeignKey(
        Asignatura,
        on_delete=models.CASCADE,
        related_name="secciones"
    )

    nrc = models.CharField(max_length=20)
    seccion = models.CharField(max_length=20)

    jornada = models.CharField(
        max_length=40,
        null=True,
        blank=True
    )
    horario = models.CharField(
        max_length=160,
        null=True,
        blank=True
    )

    estado = models.CharField(max_length=20)

    fecha_consolidacion = models.DateTimeField(
        null=True,
        blank=True
    )

    carreras = models.ManyToManyField(
        Carrera,
        through="SeccionCarrera",
        related_name="secciones"
    )

    docentes = models.ManyToManyField(
        Docente,
        through="SeccionDocente",
        related_name="secciones"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["periodo", "nrc"],
                name="unique_periodo_nrc"
            )
        ]

    def __str__(self):
        return f"{self.nrc} - {self.seccion} - {self.asignatura}"


class SeccionCarrera(models.Model):
    seccion = models.ForeignKey(
        Seccion,
        on_delete=models.CASCADE,
        related_name="seccion_carreras"
    )
    carrera = models.ForeignKey(
        Carrera,
        on_delete=models.CASCADE,
        related_name="seccion_carreras"
    )

    nivel = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )
    declaracion_as = models.BooleanField(
        null=True,
        blank=True
    )
    estudiantes_planificados = models.IntegerField(
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seccion", "carrera"],
                name="unique_seccion_carrera"
            )
        ]

    def __str__(self):
        return f"{self.seccion} - {self.carrera}"


class SeccionDocente(models.Model):
    seccion = models.ForeignKey(
        Seccion,
        on_delete=models.CASCADE,
        related_name="seccion_docentes"
    )
    docente = models.ForeignKey(
        Docente,
        on_delete=models.CASCADE,
        related_name="seccion_docentes"
    )

    tipo_contrato = models.CharField(
        max_length=80,
        null=True,
        blank=True
    )
    capacitado_as = models.BooleanField(
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seccion", "docente"],
                name="unique_seccion_docente"
            )
        ]

    def __str__(self):
        return f"{self.seccion} - {self.docente}"