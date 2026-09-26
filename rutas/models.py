from django.conf import settings
from django.db import models


class RutaPlantilla(models.Model):
    nombre = models.CharField(max_length=180)
    descripcion = models.TextField(null=True, blank=True)
    activo = models.BooleanField()

    def __str__(self):
        return self.nombre


class RutaVersion(models.Model):
    plantilla = models.ForeignKey(
        RutaPlantilla,
        on_delete=models.PROTECT,
        related_name="versiones",
    )

    creado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="versiones_ruta_creadas",
    )

    numero_version = models.IntegerField()
    estado = models.CharField(max_length=20)

    fecha_vigencia_desde = models.DateField(
        null=True,
        blank=True,
    )

    fecha_vigencia_hasta = models.DateField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["plantilla", "numero_version"],
                name="unique_version_por_ruta_plantilla",
            )
        ]

    def __str__(self):
        return f"{self.plantilla} - Versión {self.numero_version}"


class RutaActividad(models.Model):
    ruta_version = models.ForeignKey(
        RutaVersion,
        on_delete=models.CASCADE,
        related_name="actividades",
    )

    formulario_version = models.ForeignKey(
        "encuestas.FormularioVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actividades_ruta",
    )

    archivo_recurso = models.ForeignKey(
        "archivos.Archivo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actividades_ruta",
    )

    etapa = models.CharField(max_length=80)
    nombre = models.CharField(max_length=220)

    descripcion = models.TextField(
        null=True,
        blank=True,
    )

    es_obligatoria = models.BooleanField()
    orden = models.IntegerField()

    recurso_url = models.CharField(
        max_length=500,
        null=True,
        blank=True,
    )

    config_recordatorio_json = models.JSONField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.orden} - {self.nombre}"


class SeccionRuta(models.Model):
    seccion = models.OneToOneField(
        "academico.Seccion",
        on_delete=models.PROTECT,
        related_name="ruta_asignada",
    )

    ruta_version = models.ForeignKey(
        RutaVersion,
        on_delete=models.PROTECT,
        related_name="secciones_asignadas",
    )

    cerrada_por_docente = models.ForeignKey(
        "academico.Docente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rutas_cerradas",
    )

    estado = models.CharField(max_length=20)

    porcentaje_final = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    fecha_cierre = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.seccion} - {self.ruta_version}"


class SeccionActividad(models.Model):
    seccion_ruta = models.ForeignKey(
        SeccionRuta,
        on_delete=models.CASCADE,
        related_name="actividades",
    )

    ruta_actividad = models.ForeignKey(
        RutaActividad,
        on_delete=models.PROTECT,
        related_name="secciones_actividad",
    )

    completada_por_docente = models.ForeignKey(
        "academico.Docente",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actividades_ruta_completadas",
    )

    estado = models.CharField(max_length=20)

    fecha_completada = models.DateTimeField(
        null=True,
        blank=True,
    )

    observacion = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seccion_ruta", "ruta_actividad"],
                name="unique_actividad_por_seccion_ruta",
            )
        ]

    def __str__(self):
        return f"{self.seccion_ruta} - {self.ruta_actividad}"


class ExpedienteSeccion(models.Model):
    seccion = models.OneToOneField(
        "academico.Seccion",
        on_delete=models.PROTECT,
        related_name="expediente",
    )

    estado = models.CharField(max_length=20)

    fecha_creacion = models.DateTimeField()

    fecha_cierre = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Expediente - {self.seccion}"


class Evidencia(models.Model):
    expediente = models.ForeignKey(
        ExpedienteSeccion,
        on_delete=models.CASCADE,
        related_name="evidencias",
    )

    seccion_actividad = models.ForeignKey(
        SeccionActividad,
        on_delete=models.PROTECT,
        related_name="evidencias",
    )

    archivo = models.OneToOneField(
        "archivos.Archivo",
        on_delete=models.PROTECT,
        related_name="evidencia",
    )

    descripcion = models.TextField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Evidencia {self.pk}"