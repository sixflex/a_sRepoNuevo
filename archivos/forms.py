from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from core.models import Noticia
from .models import RecursoRepositorio
from .validators import get_extensiones_permitidas


# Categorías del repositorio (RF-PUB-02). Son texto en el modelo, así que
# agregar una aquí no requiere migración.
CATEGORIAS = [
    ("Formatos oficiales", "Formatos oficiales"),
    ("Guías metodológicas", "Guías metodológicas"),
    ("Documentos institucionales", "Documentos institucionales"),
    ("Reglamentos", "Reglamentos"),
    ("Otros", "Otros"),
]

# El repositorio acepta PDF, Word y Excel (RF-PUB-02), dentro de los formatos
# que permite el almacenamiento privado.
EXTENSIONES_REPOSITORIO = ["pdf", "doc", "docx", "xls", "xlsx"]


class RecursoRepositorioForm(forms.ModelForm):
    archivo_subido = forms.FileField(
        label="Archivo",
        required=False,
    )

    categoria = forms.ChoiceField(label="Categoría", choices=CATEGORIAS)

    visibilidad = forms.ChoiceField(
        label="Visibilidad",
        choices=RecursoRepositorio.VISIBILIDAD_CHOICES,
        help_text="Los privados nunca aparecen en el portal público.",
    )

    class Meta:
        model = RecursoRepositorio
        fields = ["titulo", "descripcion", "categoria", "url_externa", "visibilidad"]
        labels = {
            "titulo": "Título",
            "descripcion": "Descripción",
            "url_externa": "Enlace externo",
        }
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "url_externa": forms.URLInput(attrs={"placeholder": "https://..."}),
        }
        help_texts = {
            "url_externa": "Úsalo en vez de un archivo para enlazar un documento publicado en otro sitio.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["archivo_subido"].help_text = (
            f"PDF, Word o Excel, hasta {settings.REPOSITORIO_MAX_FILE_SIZE_MB} MB. "
            "Al editar, sube uno nuevo solo si quieres reemplazarlo."
        )
        self.fields["archivo_subido"].widget.attrs["accept"] = ",".join(
            f".{ext}" for ext in EXTENSIONES_REPOSITORIO
        )
        for nombre, campo in self.fields.items():
            clase = "form-select" if isinstance(campo, forms.ChoiceField) else "form-control"
            campo.widget.attrs.setdefault("class", clase)

    def clean_url_externa(self):
        url = (self.cleaned_data.get("url_externa") or "").strip()
        if url and not url.lower().startswith(("http://", "https://")):
            raise ValidationError("El enlace debe comenzar con http:// o https://.")
        return url or None

    def clean_archivo_subido(self):
        archivo = self.cleaned_data.get("archivo_subido")
        if archivo:
            extension = archivo.name.rsplit(".", 1)[-1].lower() if "." in archivo.name else ""
            permitidas = [e for e in EXTENSIONES_REPOSITORIO if e in get_extensiones_permitidas()]
            if extension not in permitidas:
                raise ValidationError(
                    "Formato no permitido. Solo se aceptan: "
                    + ", ".join(e.upper() for e in permitidas) + "."
                )
        return archivo

    def clean(self):
        datos = super().clean()
        tiene_archivo = bool(datos.get("archivo_subido")) or bool(
            self.instance.pk and self.instance.archivo_id
        )
        if not tiene_archivo and not datos.get("url_externa"):
            raise ValidationError("Sube un archivo o indica un enlace externo.")
        return datos


class NoticiaForm(forms.ModelForm):
    class Meta:
        model = Noticia
        fields = [
            "titulo",
            "resumen",
            "fuente",
            "url_fuente",
            "imagen_url",
            "fecha_publicacion",
            "estado",
        ]
        widgets = {
            "fecha_publicacion": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "resumen": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "fuente": forms.TextInput(attrs={"class": "form-control"}),
            "url_fuente": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "imagen_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://..."}),
            "estado": forms.Select(choices=[("PUBLICADA", "Publicada"), ("BORRADOR", "Borrador")], attrs={"class": "form-select"}),
        }

    def clean_url_fuente(self):
        url_fuente = (self.cleaned_data.get("url_fuente") or "").strip()
        if url_fuente:
            # Criterio de aceptación: las noticias no se duplican por URL
            qs = Noticia.objects.filter(url_fuente=url_fuente)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ya existe una noticia registrada con esta misma URL de fuente.")
        return url_fuente