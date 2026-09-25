from django import forms
from django.forms import modelformset_factory

from .models import FilaPlanificacion


class FilaPlanificacionForm(forms.ModelForm):
    class Meta:
        model = FilaPlanificacion

        fields = [
            "facultad_texto",
            "carrera_texto",
            "declaracion_as",
            "nrc",
            "campus_texto",
            "seccion",
            "asignatura_texto",
            "jornada",
            "horario",
            "estudiantes_planificados",
            "posible_socio_texto",
        ]

        widgets = {
            "facultad_texto": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "carrera_texto": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "declaracion_as": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "nrc": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "campus_texto": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "seccion": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "asignatura_texto": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "jornada": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "horario": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "estudiantes_planificados": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                }
            ),
            "posible_socio_texto": forms.TextInput(
                attrs={"class": "form-control"}
            ),
        }


FilaPlanificacionFormSet = modelformset_factory(
    FilaPlanificacion,
    form=FilaPlanificacionForm,
    extra=1,
    can_delete=True,
)