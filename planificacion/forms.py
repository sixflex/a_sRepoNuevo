from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseModelFormSet, formset_factory, modelformset_factory

from .models import FilaPlanificacion


class FilaPlanificacionForm(forms.ModelForm):
    class Meta:
        model = FilaPlanificacion
        fields = [
            "facultad_texto",
            "carrera_texto",
            "declaracion_as",
            "nrc",
            "seccion",
            "asignatura_texto",
            "nivel",
            "jornada",
            "horario",
            "estudiantes_planificados",
            "posible_socio_texto",
        ]
        widgets = {
            "facultad_texto": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "carrera_texto": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "declaracion_as": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "nrc": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "seccion": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "asignatura_texto": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "nivel": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "jornada": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "horario": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "estudiantes_planificados": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "min": 0,
                }
            ),
            "posible_socio_texto": forms.TextInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "Por definir",
                }
            ),
        }

    def clean_nrc(self):
        return (self.cleaned_data.get("nrc") or "").strip()


class BaseFilaPlanificacionFormSet(BaseModelFormSet):
    def clean(self):
        super().clean()

        nrc_vistos = set()

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            if not form.instance.pk:
                campos_fila = [
                    form.data.get(form.add_prefix("nrc")),
                    form.data.get(form.add_prefix("seccion")),
                    form.data.get(form.add_prefix("asignatura_texto")),
                    form.data.get(form.add_prefix("nivel")),
                    form.data.get(form.add_prefix("jornada")),
                    form.data.get(form.add_prefix("horario")),
                    form.data.get(form.add_prefix("estudiantes_planificados")),
                ]

                declaracion_as = form.data.get(
                    form.add_prefix("declaracion_as")
                )

                if (
                    not any(valor for valor in campos_fila)
                    and not declaracion_as
                ):
                    form._errors.clear()
                    continue

            nrc = (form.cleaned_data.get("nrc") or "").strip()

            if not nrc:
                continue

            if nrc in nrc_vistos:
                form.add_error(
                    "nrc",
                    "El NRC está repetido dentro de esta planificación.",
                )
            else:
                nrc_vistos.add(nrc)


FilaPlanificacionFormSet = modelformset_factory(
    FilaPlanificacion,
    form=FilaPlanificacionForm,
    formset=BaseFilaPlanificacionFormSet,
    extra=1,
    can_delete=True,
)


class DocenteFilaForm(forms.Form):
    id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )
    rut = forms.CharField(
        max_length=12,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-sm"}
        ),
    )
    nombre = forms.CharField(
        max_length=180,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-sm"}
        ),
    )
    tipo_contrato = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-sm"}
        ),
    )
    capacitado_as = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            attrs={"class": "form-select form-select-sm"},
            choices=[
                ("", "No informado"),
                ("true", "Sí"),
                ("false", "No"),
            ],
        ),
    )
    correo = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={"class": "form-control form-control-sm"}
        ),
    )
    telefono = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-sm"}
        ),
    )

    def clean(self):
        cleaned = super().clean()

        if cleaned.get("DELETE"):
            return cleaned

        campos = [
            cleaned.get("rut"),
            cleaned.get("nombre"),
            cleaned.get("tipo_contrato"),
            cleaned.get("correo"),
            cleaned.get("telefono"),
        ]

        tiene_datos = any(
            valor not in (None, "")
            for valor in campos
        ) or cleaned.get("capacitado_as") is not None

        if tiene_datos and not cleaned.get("nombre"):
            self.add_error(
                "nombre",
                "Ingrese el nombre del Docente.",
            )

        return cleaned


DocenteFilaFormSet = formset_factory(
    DocenteFilaForm,
    extra=1,
    can_delete=True,
)
