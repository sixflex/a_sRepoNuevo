from django.conf import settings
from django.db import models


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