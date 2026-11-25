import uuid

from django.conf import settings
from django.db import models


ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_BORRADOR = "BORRADOR"
ESTADO_OBSERVADA = "OBSERVADA"
ESTADO_APROBADA = "APROBADA"


class SolicitudCarta(models.Model):
    seccion = models.ForeignKey(
        "academico.Seccion",
        on_delete=models.PROTECT,
        related_name="solicitudes_carta",
    )

    campus = models.ForeignKey(
        "academico.Campus",
        on_delete=models.PROTECT,
        related_name="solicitudes_carta",
    )

    sede = models.ForeignKey(
        "academico.Sede",
        on_delete=models.PROTECT,
        related_name="solicitudes_carta",
    )

    equipo = models.ForeignKey(
        "proyectos.Equipo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_carta",
    )

    socio = models.ForeignKey(
        "socios.SocioComunitario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_carta",
    )

    solicitante_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_carta",
    )

    docente_derivador = models.ForeignKey(
    "academico.Docente",
    on_delete=models.PROTECT,
    related_name="solicitudes_carta_derivadas",
    )

    solicitante_tipo = models.CharField(
        max_length=20,
    )

    solicitante_nombre = models.CharField(
        max_length=180,
    )

    solicitante_correo = models.CharField(
        max_length=254,
    )

    solicitante_entra_id = models.CharField(
        max_length=80,
        null=True,
        blank=True,
    )

    institucion_receptora = models.CharField(
        max_length=220,
    )

    persona_receptora = models.CharField(
        max_length=180,
    )

    cargo_receptor = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )

    consideraciones = models.TextField(
        null=True,
        blank=True,
    )

    estado = models.CharField(
        max_length=30,
    )

    motivo_observacion = models.TextField(
        null=True,
        blank=True,
    )

    fecha_solicitud = models.DateTimeField()

    fecha_aprobacion = models.DateTimeField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"Solicitud {self.id} - {self.solicitante_nombre}"


class CartaEstudiante(models.Model):
    solicitud = models.ForeignKey(
        SolicitudCarta,
        on_delete=models.CASCADE,
        related_name="estudiantes",
    )

    nombre = models.CharField(
        max_length=180,
    )

    rut = models.CharField(
        max_length=12,
    )

    orden = models.SmallIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["solicitud", "orden"],
                name="unique_orden_estudiante_por_solicitud",
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.rut}"


class CartaDocumento(models.Model):
    solicitud = models.ForeignKey(
        SolicitudCarta,
        on_delete=models.CASCADE,
        related_name="documentos",
    )

    archivo = models.OneToOneField(
        "archivos.Archivo",
        on_delete=models.PROTECT,
        related_name="documento_carta",
    )

    generado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="documentos_carta_generados",
    )

    numero_version = models.IntegerField()

    tipo = models.CharField(
        max_length=20,
    )

    fecha_generacion = models.DateTimeField()

    hash_documento = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )



    plantilla = models.ForeignKey(
        "cartas.PlantillaCarta",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="documentos",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["solicitud", "numero_version"],
                name="unique_version_documento_por_solicitud",
            )
        ]

    def __str__(self):
        return (
            f"Carta solicitud {self.solicitud_id} "
            f"- Versión {self.numero_version}"
        )


class EnlaceSolicitudCarta(models.Model):
    """SP6-T08: enlace público para que el estudiante informante solicite la carta."""

    seccion = models.ForeignKey(
        "academico.Seccion",
        on_delete=models.PROTECT,
        related_name="enlaces_solicitud_carta",
    )

    creado_por_docente = models.ForeignKey(
        "academico.Docente",
        on_delete=models.PROTECT,
        related_name="enlaces_solicitud_carta_creados",
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
        return f"Enlace solicitud carta - {self.seccion}"


class PlantillaCarta(models.Model):
    """
    Word oficial de la Carta de Presentación que sube el Coordinador (el de
    "combinar correspondencia", con su firma, el logo y su tarjeta). El portal
    toma de él las imágenes para armar cada carta (cartas/plantilla_oficial.py).

    Se guarda en el almacenamiento privado (nunca en static/media, RN-07). Solo
    una está activa; las anteriores se conservan porque cada CartaDocumento
    indica con cuál salió.
    """

    archivo = models.OneToOneField(
        "archivos.Archivo",
        on_delete=models.PROTECT,
        related_name="plantilla_carta",
    )
    cargada_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="plantillas_carta_cargadas",
    )
    fecha_carga = models.DateTimeField(auto_now_add=True)
    activa = models.BooleanField(default=False)
    observacion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-fecha_carga"]
        constraints = [
            models.UniqueConstraint(
                fields=["activa"],
                condition=models.Q(activa=True),
                name="una_plantilla_carta_activa",
            )
        ]

    def __str__(self):
        return f"{self.archivo.nombre_original} ({self.fecha_carga:%d-%m-%Y})"
