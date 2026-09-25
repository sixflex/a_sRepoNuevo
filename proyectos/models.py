import uuid

from django.conf import settings
from django.db import models

from academico.models import Seccion


class ProyectoAS(models.Model):
    nombre = models.CharField(max_length=220)
    descripcion = models.TextField(null=True, blank=True)
    servicio_propuesto = models.TextField(null=True, blank=True)
    estado = models.CharField(max_length=30)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    resumen_publico = models.TextField(null=True, blank=True)
    es_publico = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proyecto A+S"
        verbose_name_plural = "Proyectos A+S"

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    seccion = models.ForeignKey(
        Seccion,
        on_delete=models.PROTECT,
        related_name="equipos",
    )
    proyecto = models.ForeignKey(
        ProyectoAS,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipos",
    )
    numero_grupo = models.IntegerField()
    informante_nombre = models.CharField(max_length=180)
    informante_correo = models.CharField(max_length=254)
    informante_entra_id = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seccion", "numero_grupo"],
                name="unique_numero_grupo_por_seccion",
            )
        ]

    def __str__(self):
        return f"{self.seccion} - Grupo {self.numero_grupo}"


class IntegranteEquipo(models.Model):
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="integrantes",
    )
    rut = models.CharField(max_length=12)
    nombres = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=120)
    correo_institucional = models.CharField(max_length=254)
    es_informante = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["equipo", "rut"],
                name="unique_rut_por_equipo",
            )
        ]

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class Etiqueta(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class IntegranteEtiqueta(models.Model):
    integrante = models.ForeignKey(
        IntegranteEquipo,
        on_delete=models.CASCADE,
        related_name="etiquetas_asignadas",
    )
    etiqueta = models.ForeignKey(
        Etiqueta,
        on_delete=models.PROTECT,
        related_name="integrantes_asignados",
    )
    asignado_por_docente = models.ForeignKey(
    "academico.Docente",
    on_delete=models.PROTECT,
    related_name="etiquetas_asignadas",
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["integrante", "etiqueta"],
                name="unique_etiqueta_por_integrante",
            )
        ]


class EnlaceRegistroEquipo(models.Model):
    seccion = models.ForeignKey(
        Seccion,
        on_delete=models.PROTECT,
        related_name="enlaces_registro_equipo",
    )
    creado_por_docente = models.ForeignKey(
        "academico.Docente",
        on_delete=models.PROTECT,
        related_name="enlaces_registro_equipo_creados",
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    fecha_inicio = models.DateTimeField()
    fecha_expiracion = models.DateTimeField(
        null=True,
        blank=True,
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"Registro equipo - {self.seccion}"