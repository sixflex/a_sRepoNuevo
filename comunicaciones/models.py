from django.db import models


class PlantillaCorreo(models.Model):
    codigo = models.CharField(max_length=80, unique=True)
    asunto_template = models.CharField(max_length=255)
    cuerpo_template = models.TextField()
    activo = models.BooleanField()

    def __str__(self):
        return self.codigo


class EnvioCorreo(models.Model):
    RESULTADO_CHOICES = [
        ("PENDIENTE", "Pendiente"),
        ("OK", "OK"),
        ("ERROR", "Error"),
    ]

    plantilla = models.ForeignKey(
        PlantillaCorreo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios",
    )

    carta_documento = models.ForeignKey(
        "cartas.CartaDocumento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_correo",
    )

    postulacion = models.ForeignKey(
        "socios.PostulacionSocio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_correo",
    )

    invitacion_cierre = models.ForeignKey(
        "socios.InvitacionCierre",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="envios_correo",
    )

    remitente = models.CharField(max_length=254)
    destinatario = models.CharField(max_length=254)
    asunto = models.CharField(max_length=255)
    cuerpo = models.TextField()

    fecha_envio = models.DateTimeField(
        null=True,
        blank=True,
    )

    resultado = models.CharField(
        max_length=20,
        choices=RESULTADO_CHOICES,
    )

    detalle_error = models.TextField(
        null=True,
        blank=True,
    )

    numero_intento = models.IntegerField()

    def __str__(self):
        return f"{self.destinatario} - {self.asunto}"