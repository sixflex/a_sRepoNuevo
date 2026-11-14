from django import forms

from .models import Noticia
from .noticias import normalizar_url


class NoticiaForm(forms.ModelForm):
    """Noticia agregada por enlace (RF-PUB-04). No se repite una URL (RF-PUB-03 CA1)."""

    url_fuente = forms.URLField(
        label="Enlace de la noticia", max_length=500, assume_scheme="https",
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://www.uautonoma.cl/noticias/..."}),
    )
    imagen_url = forms.URLField(
        label="Imagen", max_length=500, required=False, assume_scheme="https",
        help_text="Dirección de la imagen. Si la dejas vacía, la tarjeta sale sin foto.",
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
    )
    fecha_publicacion = forms.DateField(
        label="Fecha de la noticia",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = Noticia
        fields = ["url_fuente", "titulo", "resumen", "imagen_url", "fecha_publicacion", "fuente"]
        labels = {"titulo": "Título", "resumen": "Resumen", "fuente": "Fuente"}
        help_texts = {
            "resumen": "Dos o tres líneas. Es lo que se lee en la tarjeta del portal.",
            "fuente": "Quién publicó la noticia.",
        }
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "resumen": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "fuente": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_url_fuente(self):
        url = normalizar_url(self.cleaned_data["url_fuente"])
        repetidas = Noticia.objects.filter(url_fuente__in=[url, url + "/"])
        if self.instance.pk:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise forms.ValidationError("Esta noticia ya está agregada.")
        return url

    def clean_fecha_publicacion(self):
        from datetime import datetime, time

        from django.utils import timezone

        return timezone.make_aware(datetime.combine(self.cleaned_data["fecha_publicacion"], time(12)))
