from django import forms
from django.forms import BaseModelFormSet, formset_factory, modelformset_factory

from academico.constantes import JORNADAS, NIVELES, TIPOS_CONTRATO
from academico.models import Carrera, Facultad

from .models import FilaPlanificacion
from .textos import DIAS_SEMANA, leer_horario, texto_horario


class SelectConValorGuardado(forms.Select):
    """
    Lista de opciones para un campo que se guarda como texto (RNF-USA-03).
    Si la fila trae un valor que no está en la lista (borrador antiguo o
    escrito a mano), se agrega como opción para no perderlo: lo que se envía
    sigue siendo el mismo texto que resuelve planificacion/services.py.
    """

    def _valores(self):
        for valor, etiqueta in self.choices:
            if isinstance(etiqueta, (list, tuple)):
                yield from (str(opcion) for opcion, _ in etiqueta)
            else:
                yield str(valor)

    def get_context(self, name, value, attrs):
        if value not in (None, "") and str(value) not in set(self._valores()):
            self.choices = [*self.choices, (value, value)]

        return super().get_context(name, value, attrs)


def _lista(opciones, vacia="Seleccione"):
    return SelectConValorGuardado(
        attrs={"class": "form-select form-select-sm"},
        choices=[("", vacia), *opciones],
    )


def opciones_planificacion():
    """
    Facultades y carreras activas, por nombre: la consolidación busca la
    carrera por nombre (planificacion/services.py, _resolver_carrera).
    """
    carreras = {}

    for carrera in (
        Carrera.objects.filter(activo=True)
        .select_related("facultad")
        .order_by("facultad__nombre", "nombre")
    ):
        carreras.setdefault(carrera.facultad.nombre, []).append(
            (carrera.nombre, carrera.nombre)
        )

    return {
        "facultades": [
            (nombre, nombre)
            for nombre in Facultad.objects.filter(activo=True)
            .order_by("nombre")
            .values_list("nombre", flat=True)
        ],
        "carreras": list(carreras.items()),
    }


class HorarioWidget(forms.MultiWidget):
    """Checks Lu a Sá y hora de inicio; un horario antiguo con otro formato se muestra tal cual."""

    template_name = "planificacion/widgets/horario.html"

    def __init__(self, attrs=None):
        super().__init__(
            [
                forms.CheckboxSelectMultiple(choices=DIAS_SEMANA),
                forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "form-control form-control-sm"}),
                forms.HiddenInput(),
            ],
            attrs,
        )

    def decompress(self, value):
        leido = leer_horario(value)
        if leido:
            return [leido[0], leido[1], ""]
        return [[], "", value or ""]


class HorarioField(forms.MultiValueField):
    """Se guarda como texto en FilaPlanificacion.horario, por ejemplo «Lu, Mi 08:30» (RNF-USA-03)."""

    widget = HorarioWidget

    def __init__(self, **kwargs):
        super().__init__(
            fields=[
                forms.MultipleChoiceField(choices=DIAS_SEMANA, required=False),
                forms.TimeField(
                    required=False,
                    input_formats=["%H:%M"],
                    error_messages={"invalid": "Ingrese una hora válida, por ejemplo 08:30."},
                ),
                forms.CharField(required=False),
            ],
            require_all_fields=False,
            required=False,
            **kwargs,
        )

    def compress(self, data_list):
        dias, hora, anterior = (list(data_list) + [None, None, None])[:3]
        if not dias and not hora:
            return anterior or ""
        if not dias:
            raise forms.ValidationError("Marque al menos un día para la hora de inicio.")
        if not hora:
            raise forms.ValidationError("Ingrese la hora de inicio de los días marcados.")
        return texto_horario(dias, hora)


class FilaPlanificacionForm(forms.ModelForm):
    horario = HorarioField(label="Horario")

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
        ]
        widgets = {
            "facultad_texto": _lista([]),
            "carrera_texto": _lista([]),
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
            "nivel": _lista(NIVELES, "—"),
            "jornada": _lista(JORNADAS, "—"),
            "estudiantes_planificados": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "min": 0,
                }
            ),
        }

    def __init__(self, *args, opciones=None, **kwargs):
        super().__init__(*args, **kwargs)
        opciones = opciones or opciones_planificacion()
        self.fields["facultad_texto"].widget.choices = [("", "Seleccione"), *opciones["facultades"]]
        self.fields["carrera_texto"].widget.choices = [("", "Seleccione"), *opciones["carreras"]]

    def clean_nrc(self):
        return (self.cleaned_data.get("nrc") or "").strip()


class BaseFilaPlanificacionFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        # Las opciones se consultan una vez para todas las filas.
        kwargs.setdefault("form_kwargs", {"opciones": opciones_planificacion()})
        super().__init__(*args, **kwargs)
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
                    *form.data.getlist(form.add_prefix("horario_0"), []),
                    form.data.get(form.add_prefix("horario_1")),
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
    extra=0,
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
            attrs={"class": "form-control form-control-sm", "placeholder": "12345678-5"}
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
        widget=_lista(TIPOS_CONTRATO, "No informado"),
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
            attrs={"class": "form-control form-control-sm", "placeholder": "correo@dominio.cl"}
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
    extra=0,
    can_delete=True,
)


class SocioFilaForm(forms.Form):
    """Posible socio comunitario de la fila: todo es opcional (RF-ACA-03)."""

    nombre = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-sm", "placeholder": "Organización"}
        ),
    )
    correo = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={"class": "form-control form-control-sm", "placeholder": "correo@dominio.cl"}
        ),
    )
    rubro = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-sm", "placeholder": "Negocio o rubro"}
        ),
    )


SocioFilaFormSet = formset_factory(
    SocioFilaForm,
    extra=0,
    can_delete=True,
)
