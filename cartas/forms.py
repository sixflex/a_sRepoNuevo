from django import forms

from .models import SolicitudCarta


class SolicitudCartaForm(forms.ModelForm):
    class Meta:
        model = SolicitudCarta
        fields = [
            "equipo",
            "institucion_receptora",
            "persona_receptora",
            "cargo_receptor",
            "consideraciones",
        ]
        widgets = {
            "equipo": forms.Select(
                attrs={"class": "form-select"}
            ),
            "institucion_receptora": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "persona_receptora": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "cargo_receptor": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "consideraciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, seccion=None, **kwargs):
        super().__init__(*args, **kwargs)

        if seccion is not None:
            self.fields["equipo"].queryset = (
                seccion.equipos
                .select_related("socio_comunitario")
                .order_by("numero_grupo")
            )

        self.fields["equipo"].required = False
        self.fields["cargo_receptor"].required = False
        self.fields["consideraciones"].required = False

        self.fields["equipo"].label = "Equipo"
        self.fields["institucion_receptora"].label = "Institución receptora"
        self.fields["persona_receptora"].label = "Persona receptora"
        self.fields["cargo_receptor"].label = "Cargo de la persona receptora"
        self.fields["consideraciones"].label = "Consideraciones"