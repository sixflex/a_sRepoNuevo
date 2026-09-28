import uuid

from django.db import models


class PlanificacionEnlace(models.Model):
    unidad_academica = models.ForeignKey(
        "academico.UnidadAcademica",
        on_delete=models.PROTECT,
        related_name="enlaces_planificacion",
    )

    campus = models.ForeignKey(
        "academico.Campus",
        on_delete=models.PROTECT,
        related_name="enlaces_planificacion",
    )

    periodo = models.ForeignKey(
        "academico.PeriodoAcademico",
        on_delete=models.PROTECT,
        related_name="enlaces_planificacion",
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    destinatario_nombre = models.CharField(max_length=180)

    destinatario_correo = models.CharField(max_length=254)

    fecha_emision = models.DateTimeField()

    fecha_expiracion = models.DateTimeField(
        null=True,
        blank=True,
    )

    activo = models.BooleanField()

    def __str__(self):
        return f"{self.destinatario_nombre} - {self.periodo}"


class Planificacion(models.Model):
    enlace = models.OneToOneField(
        PlanificacionEnlace,
        on_delete=models.PROTECT,
        related_name="planificacion",
    )

    estado = models.CharField(max_length=20)

    fecha_guardado = models.DateTimeField(
        null=True,
        blank=True,
    )

    fecha_envio_final = models.DateTimeField(
        null=True,
        blank=True,
    )

    filas_recibidas = models.IntegerField()

    filas_aceptadas = models.IntegerField()

    filas_observadas = models.IntegerField()

    def __str__(self):
        return f"Planificación {self.id} - {self.estado}"


class FilaPlanificacion(models.Model):
    planificacion = models.ForeignKey(
        Planificacion,
        on_delete=models.CASCADE,
        related_name="filas",
    )

    numero_fila = models.IntegerField()

    facultad_texto = models.CharField(
        max_length=180,
        null=True,
        blank=True,
    )

    carrera_texto = models.CharField(
        max_length=180,
        null=True,
        blank=True,
    )

    declaracion_as = models.BooleanField(
        null=True,
        blank=True,
    )

    nrc = models.CharField(max_length=20)

    campus_texto = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )

    seccion = models.CharField(max_length=20)

    asignatura_texto = models.CharField(max_length=180)

    nivel = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    jornada = models.CharField(
        max_length=40,
        null=True,
        blank=True,
    )

    horario = models.CharField(
        max_length=160,
        null=True,
        blank=True,
    )

    estudiantes_planificados = models.IntegerField(
        null=True,
        blank=True,
    )

    posible_socio_texto = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    estado_validacion = models.CharField(max_length=20)

    campus_resuelto = models.ForeignKey(
        "academico.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filas_planificacion_resueltas",
    )

    carrera_resuelta = models.ForeignKey(
        "academico.Carrera",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filas_planificacion_resueltas",
    )

    asignatura_resuelta = models.ForeignKey(
        "academico.Asignatura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filas_planificacion_resueltas",
    )

    seccion_resultante = models.ForeignKey(
        "academico.Seccion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filas_planificacion_resultantes",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["planificacion", "numero_fila"],
                name="unique_numero_fila_por_planificacion",
            )
        ]

    def __str__(self):
        return f"Planificación {self.planificacion_id} - Fila {self.numero_fila}"


class FilaPlanificacionDocente(models.Model):
    fila = models.ForeignKey(
        FilaPlanificacion,
        on_delete=models.CASCADE,
        related_name="docentes",
    )

    docente_resuelto = models.ForeignKey(
        "academico.Docente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filas_planificacion_resueltas",
    )

    rut = models.CharField(
        max_length=12,
        null=True,
        blank=True,
    )

    nombre = models.CharField(
        max_length=180,
        null=True,
        blank=True,
    )

    tipo_contrato = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )

    capacitado_as = models.BooleanField(
        null=True,
        blank=True,
    )

    correo = models.CharField(
        max_length=254,
        null=True,
        blank=True,
    )

    telefono = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.nombre or f"Docente fila {self.fila_id}"


class PlanificacionError(models.Model):
    fila = models.ForeignKey(
        FilaPlanificacion,
        on_delete=models.CASCADE,
        related_name="errores",
    )

    campo = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )

    codigo = models.CharField(
        max_length=40,
        null=True,
        blank=True,
    )

    mensaje = models.TextField()

    def __str__(self):
        return f"Error fila {self.fila_id} - {self.codigo or 'Sin código'}"