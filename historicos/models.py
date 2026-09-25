from django.conf import settings
from django.db import models


class CargaHistorica(models.Model):
    archivo = models.OneToOneField(
        "archivos.Archivo",
        on_delete=models.PROTECT,
        related_name="carga_historica",
    )

    responsable_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cargas_historicas",
    )

    tipo_origen = models.CharField(max_length=60)

    hoja = models.CharField(
        max_length=120,
        null=True,
        blank=True,
    )

    fecha_carga = models.DateTimeField()

    estado = models.CharField(max_length=20)

    total_filas = models.IntegerField()

    aceptadas = models.IntegerField()

    observadas = models.IntegerField()

    omitidas = models.IntegerField()

    def __str__(self):
        return f"{self.tipo_origen} - {self.fecha_carga}"


class CargaMapeo(models.Model):
    carga = models.ForeignKey(
        CargaHistorica,
        on_delete=models.CASCADE,
        related_name="mapeos",
    )

    columna_origen = models.CharField(max_length=180)

    campo_destino = models.CharField(max_length=180)

    def __str__(self):
        return f"{self.columna_origen} -> {self.campo_destino}"


class CargaFila(models.Model):
    carga = models.ForeignKey(
        CargaHistorica,
        on_delete=models.CASCADE,
        related_name="filas",
    )

    respuesta_resultante = models.ForeignKey(
        "encuestas.RespuestaFormulario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filas_historicas",
    )

    socio_resultante = models.ForeignKey(
        "socios.SocioComunitario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filas_historicas",
    )

    participacion_resultante = models.ForeignKey(
        "socios.ParticipacionSocio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filas_historicas",
    )

    numero_fila = models.IntegerField()

    datos_raw_json = models.JSONField()

    estado = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["carga", "numero_fila"],
                name="unique_numero_fila_por_carga",
            )
        ]

    def __str__(self):
        return f"Carga {self.carga_id} - Fila {self.numero_fila}"


class CargaError(models.Model):
    fila = models.ForeignKey(
        CargaFila,
        on_delete=models.CASCADE,
        related_name="errores",
    )

    campo = models.CharField(
        max_length=120,
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