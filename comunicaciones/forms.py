from django import forms

from .configuracion import SERVIDORES
from .models import ConfiguracionCorreo


class ConfiguracionCorreoForm(forms.ModelForm):
    """Cuenta de envío. La clave no se muestra nunca; en blanco = se mantiene."""

    clave = forms.CharField(
        label="Clave de aplicación",
        required=False,
        strip=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = ConfiguracionCorreo
        fields = [
            "remitente_nombre", "remitente_correo", "responder_a",
            "proveedor", "servidor_smtp", "puerto", "usar_tls", "activo",
        ]
        labels = {
            "remitente_nombre": "Nombre que verán los destinatarios",
            "remitente_correo": "Correo desde el que se envía",
            "responder_a": "Las respuestas llegan a (opcional)",
            "proveedor": "Tipo de cuenta",
            "servidor_smtp": "Servidor SMTP",
            "puerto": "Puerto",
            "usar_tls": "Usar conexión segura (TLS)",
            "activo": "Enviar los correos del portal desde esta cuenta",
        }
        help_texts = {
            "remitente_nombre": "Ej.: Coordinación A+S.",
            "remitente_correo": "Puede ser tu correo mientras DTI entrega el de A+S; después solo lo cambias aquí.",
            "responder_a": "Si quieres que las respuestas lleguen a otro correo.",
            "activo": "Si lo desactivas, el portal usa la cuenta configurada en el servidor.",
        }
        widgets = {
            "remitente_correo": forms.EmailInput(attrs={"placeholder": "coordinacion.as@uautonoma.cl"}),
            "responder_a": forms.EmailInput(attrs={"placeholder": "opcional"}),
        }

    def __init__(self, *args, tiene_clave=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.tiene_clave = tiene_clave
        self.fields["servidor_smtp"].required = False
        self.fields["clave"].help_text = (
            "Ya hay una clave guardada; escribe una solo si quieres cambiarla. " if tiene_clave else ""
        ) + (
            "Gmail: crea una “contraseña de aplicación” en myaccount.google.com/apppasswords. "
            "Microsoft: tu clave, si DTI tiene habilitado el envío SMTP para tu cuenta."
        )
        for nombre, campo in self.fields.items():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(campo.widget, forms.Select):
                campo.widget.attrs.setdefault("class", "form-select")
            else:
                campo.widget.attrs.setdefault("class", "form-control")

    def clean_remitente_correo(self):
        return self.cleaned_data["remitente_correo"].strip().lower()

    def clean(self):
        datos = super().clean()
        proveedor = datos.get("proveedor")
        if proveedor in SERVIDORES:
            datos["servidor_smtp"], datos["puerto"], datos["usar_tls"] = SERVIDORES[proveedor]
        elif not datos.get("servidor_smtp"):
            self.add_error("servidor_smtp", "Indica el servidor SMTP de tu proveedor.")
        if datos.get("activo") and not datos.get("clave") and not self.tiene_clave:
            self.add_error("clave", "Escribe la clave de aplicación para poder enviar desde esta cuenta.")
        return datos


class CorreoPruebaForm(forms.Form):
    destinatario = forms.EmailField(
        label="Enviar un correo de prueba a",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
