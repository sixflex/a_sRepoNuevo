from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

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

class RutaActividadQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.exclude(ruta_version__estado="BORRADOR").exists():
            raise ValidationError(
                "No se pueden modificar actividades de una versión publicada."
            )
        return super().update(**kwargs)

    def delete(self):
        if self.exclude(ruta_version__estado="BORRADOR").exists():
            raise ValidationError(
                "No se pueden eliminar actividades de una versión publicada."
            )
        return super().delete()
    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        objetos = list(objs)
        versiones = {
            objeto.ruta_version_id
            for objeto in objetos
            if objeto.ruta_version_id is not None
        }

        if RutaVersion.objects.filter(
            pk__in=versiones
        ).exclude(estado="BORRADOR").exists():
            raise ValidationError(
                "No se pueden agregar actividades a una versión publicada."
            )

        return super().bulk_create(
            objetos,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )

    def bulk_update(self, objs, fields, batch_size=None):
        ids = [obj.pk for obj in objs if obj.pk is not None]

        if RutaActividad.objects.filter(
            pk__in=ids
        ).exclude(ruta_version__estado="BORRADOR").exists():
            raise ValidationError(
                "No se pueden modificar actividades de una versión publicada."
            )

        return super().bulk_update(objs, fields, batch_size=batch_size)

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
    objects = RutaActividadQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if self.pk is None:
            if self.ruta_version.estado != "BORRADOR":
                raise ValidationError(
                    "No se pueden agregar actividades a una versión publicada."
                )
        else:
            actividad_original = RutaActividad.objects.select_related(
                "ruta_version"
            ).get(pk=self.pk)

            campos = [
                "ruta_version_id",
                "formulario_version_id",
                "archivo_recurso_id",
                "etapa",
                "nombre",
                "descripcion",
                "es_obligatoria",
                "orden",
                "recurso_url",
                "config_recordatorio_json",
            ]

            hubo_cambios = any(
                getattr(self, campo) != getattr(actividad_original, campo)
                for campo in campos
            )

            if hubo_cambios and (
                actividad_original.ruta_version.estado != "BORRADOR"
                or self.ruta_version.estado != "BORRADOR"
            ):
                raise ValidationError(
                    "No se pueden modificar actividades de una versión publicada."
                )

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.ruta_version.estado != "BORRADOR":
            raise ValidationError(
                "No se pueden eliminar actividades de una versión publicada."
            )

        super().delete(*args, **kwargs)

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