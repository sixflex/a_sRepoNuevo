import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

class ClasificacionSocio(models.Model):
    nombre = models.CharField(
        max_length=120,
        unique=True,
    )

    activo = models.BooleanField()

    def __str__(self):
        return self.nombre


class Comuna(models.Model):
    nombre = models.CharField(max_length=120)

    region = models.CharField(max_length=120)

    lat_centro = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    lon_centro = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    activo = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["nombre", "region"],
                name="unique_comuna_por_region",
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.region}"


class SocioComunitario(models.Model):
    clasificacion = models.ForeignKey(
        ClasificacionSocio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="socios",
    )

    comuna = models.ForeignKey(
        Comuna,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="socios",
    )

    rut = models.CharField(
        max_length=12,
        unique=True,
        null=True,
        blank=True,
    )

    nombre_organizacion = models.CharField(max_length=220)

    clasificacion_otra = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )

    direccion_exacta = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    centro_servicio = models.CharField(
        max_length=180,
        null=True,
        blank=True,
    )

    estado_revision = models.CharField(max_length=30)

    es_provisional = models.BooleanField()

    activo = models.BooleanField()

    fecha_creacion = models.DateTimeField()

    def __str__(self):
        return self.nombre_organizacion
    
    @property
    def solo_historial(self):
        """Conservado solo en historial (CDE-65)."""
        return (not self.activo) or self.estado_revision == "TRABAJO_TERMINADO"


class ContactoSocio(models.Model):
    socio = models.ForeignKey(
        SocioComunitario,
        on_delete=models.CASCADE,
        related_name="contactos",
    )

    nombre = models.CharField(max_length=180)

    cargo = models.CharField(
        max_length=120,
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

    es_principal = models.BooleanField()

    activo = models.BooleanField()

    def __str__(self):
        return f"{self.nombre} - {self.socio}"


class ParticipacionSocio(models.Model):
    socio = models.ForeignKey(
        SocioComunitario,
        on_delete=models.PROTECT,
        related_name="participaciones",
    )

    equipo = models.ForeignKey(
        "proyectos.Equipo",
        on_delete=models.PROTECT,
        related_name="participaciones_socios",
    )

    proyecto = models.ForeignKey(
        "proyectos.ProyectoAS",
        on_delete=models.PROTECT,
        related_name="participaciones_socios",
    )

    sede = models.ForeignKey(
        "academico.Sede",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participaciones_socios",
    )

    campus = models.ForeignKey(
        "academico.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participaciones_socios",
    )

    periodo = models.ForeignKey(
        "academico.PeriodoAcademico",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participaciones_socios",
    )

    carrera = models.ForeignKey(
        "academico.Carrera",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participaciones_socios",
    )

    asignatura = models.ForeignKey(
        "academico.Asignatura",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participaciones_socios",
    )

    seccion = models.ForeignKey(
        "academico.Seccion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participaciones_socios",
    )

    servicio_realizado = models.TextField(
        null=True,
        blank=True,
    )

    beneficiarios_estimados = models.IntegerField(
        null=True,
        blank=True,
    )

    evaluacion = models.SmallIntegerField(
        null=True,
        blank=True,
    )

    comentario = models.TextField(
        null=True,
        blank=True,
    )

    fecha_inicio = models.DateField(
        null=True,
        blank=True,
    )

    fecha_fin = models.DateField(
        null=True,
        blank=True,
    )

    origen = models.CharField(max_length=30)

    def __str__(self):
        return f"{self.socio} - {self.proyecto}"


class InvitacionCierre(models.Model):
    seccion_ruta = models.ForeignKey(
        "rutas.SeccionRuta",
        on_delete=models.PROTECT,
        related_name="invitaciones_cierre",
    )

    socio = models.ForeignKey(
        SocioComunitario,
        on_delete=models.PROTECT,
        related_name="invitaciones_cierre",
    )

    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    modo_contacto = models.CharField(max_length=20)

    fecha_envio = models.DateTimeField(
        null=True,
        blank=True,
    )

    respuesta = models.CharField(max_length=20)

    fecha_respuesta = models.DateTimeField(
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
                fields=["seccion_ruta", "socio"],
                name="unique_invitacion_cierre_seccion_socio",
            )
        ]

    def __str__(self):
        return f"Invitación {self.seccion_ruta_id} - {self.socio_id}"


class Convocatoria(models.Model):
    formulario_version = models.ForeignKey(
        "encuestas.FormularioVersion",
        on_delete=models.PROTECT,
        related_name="convocatorias",
    )

    nombre = models.CharField(max_length=220)

    descripcion = models.TextField(
        null=True,
        blank=True,
    )

    fecha_inicio = models.DateTimeField()

    fecha_fin = models.DateTimeField(
        null=True,
        blank=True,
    )

    estado = models.CharField(max_length=20)

    def __str__(self):
        return self.nombre


class PostulacionSocio(models.Model):
    convocatoria = models.ForeignKey(
        Convocatoria,
        on_delete=models.PROTECT,
        related_name="postulaciones",
    )

    respuesta_formulario = models.OneToOneField(
        "encuestas.RespuestaFormulario",
        on_delete=models.PROTECT,
        related_name="postulacion_socio",
    )

    socio = models.ForeignKey(
        SocioComunitario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="postulaciones",
    )

    revisado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="postulaciones_socios_revisadas",
    )

    estado = models.CharField(max_length=30)

    motivo_rechazo = models.TextField(
        null=True,
        blank=True,
    )

    fecha_recepcion = models.DateTimeField()

    fecha_revision = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Postulación {self.id} - {self.estado}"


class HistorialEstadoSocio(models.Model):
    socio = models.ForeignKey(
        SocioComunitario,
        on_delete=models.CASCADE,
        related_name="historial_estados",
    )
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo = models.CharField(max_length=30)
    provisional_anterior = models.BooleanField(default=False)
    provisional_nuevo = models.BooleanField(default=False)
    cambiado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cambios_estado_socios",
    )
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.socio} · {self.estado_anterior} → {self.estado_nuevo}"