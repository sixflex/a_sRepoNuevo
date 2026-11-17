from django.conf import settings
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

class ConfiguracionCorreo(models.Model):
    """
    Cuenta desde la que el portal envía sus correos automáticos (avisos,
    cartas, encuestas). La elige el Coordinador en Configuración, así puede
    usar su propio correo mientras DTI no entregue el de A+S y cambiarlo
    después sin tocar el servidor. Una sola fila (pk=1).

    La clave de aplicación se guarda cifrada (comunicaciones/configuracion.py)
    y nunca se muestra. Si `activo` es False se usa la cuenta del servidor
    (.env / Render: EMAIL_HOST_USER, EMAIL_HOST_PASSWORD).
    """

    PROVEEDOR_CHOICES = [
        ("MICROSOFT", "Microsoft 365 / Outlook (cuentas de la U)"),
        ("GMAIL", "Gmail"),
        ("OTRO", "Otro servidor"),
    ]

    remitente_nombre = models.CharField(max_length=120, default="Coordinación A+S")
    remitente_correo = models.EmailField(max_length=254)
    responder_a = models.EmailField(max_length=254, blank=True)
    proveedor = models.CharField(max_length=20, choices=PROVEEDOR_CHOICES, default="MICROSOFT")
    servidor_smtp = models.CharField(max_length=120)
    puerto = models.PositiveIntegerField(default=587)
    usar_tls = models.BooleanField(default=True)
    clave_cifrada = models.TextField(blank=True)
    activo = models.BooleanField(default=False)
    fecha_verificacion = models.DateTimeField(null=True, blank=True)
    modificado_por_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "configuración de correo"
        verbose_name_plural = "configuración de correo"

    def __str__(self):
        return f"{self.remitente_nombre} <{self.remitente_correo}>"
