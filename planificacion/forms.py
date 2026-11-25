from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseModelFormSet, formset_factory, modelformset_factory

from academico.constantes import JORNADAS, NIVELES, TIPOS_CONTRATO
from academico.models import Carrera, Facultad
from core.validators import validar_rut_chileno

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


def opciones_planificacion(facultad=None, campus=None):
    """
    Facultades y carreras activas, por nombre: la consolidación busca la
    carrera por nombre (planificacion/services.py, _resolver_carrera).
    Con la facultad del enlace, esa queda fija y solo se ofrecen sus carreras;
    con el campus del enlace, solo las que se imparten ahí (CarreraCampus).
    """
    carreras = {}
    consulta = Carrera.objects.filter(activo=True).select_related("facultad")
    if facultad is not None:
        consulta = consulta.filter(facultad=facultad)
    if campus is not None:
        consulta = consulta.filter(campus=campus)

    for carrera in consulta.order_by("facultad__nombre", "nombre"):
        carreras.setdefault(carrera.facultad.nombre, []).append(
            (carrera.nombre, carrera.nombre)
        )

    if facultad is not None:
        return {
            "facultades": [(facultad.nombre, facultad.nombre)],

            "carreras": carreras.get(facultad.nombre, []),
            "facultad_fija": facultad.nombre,
        }

    return {
        "facultades": [
            (nombre, nombre)
            for nombre in Facultad.objects.filter(activo=True)
            .order_by("nombre")
            .values_list("nombre", flat=True)
        ],
        "carreras": list(carreras.items()),
        "facultad_fija": None,
    }


def _input_hora():
    return forms.TimeInput(format="%H:%M", attrs={"type": "time", "class": "form-control form-control-sm"})


class HorarioWidget(forms.MultiWidget):
    """
    Checks Lu a Sá y una hora de inicio por cada día marcado (una clase puede
    ser martes 17:00 y jueves 20:00). Subwidgets: 0 = días, 1..6 = hora de
    cada día en el orden de DIAS_SEMANA, 7 = horario antiguo con otro formato.
    """

    template_name = "planificacion/widgets/horario.html"

    def __init__(self, attrs=None):
        super().__init__(
            [
                forms.CheckboxSelectMultiple(choices=DIAS_SEMANA),
                *(_input_hora() for _ in DIAS_SEMANA),
                forms.HiddenInput(),
            ],
            attrs,
        )

    def decompress(self, value):
        horas = leer_horario(value)
        if horas:
            return [list(horas), *(horas.get(codigo, "") for codigo, _ in DIAS_SEMANA), ""]
        return [[], *("" for _ in DIAS_SEMANA), value or ""]

    def get_context(self, name, value, attrs):
        contexto = super().get_context(name, value, attrs)
        subwidgets = contexto["widget"]["subwidgets"]
        contexto["widget"]["horas_por_dia"] = [
            {"codigo": codigo, "nombre": nombre, "hora": hora}
            for (codigo, nombre), hora in zip(DIAS_SEMANA, subwidgets[1:-1])
        ]
        return contexto


class HorarioField(forms.MultiValueField):
    """Se guarda como texto en FilaPlanificacion.horario, por ejemplo «Martes 17:00, Jueves 20:00» (RNF-USA-03)."""

    widget = HorarioWidget

    def __init__(self, **kwargs):
        super().__init__(
            fields=[
                forms.MultipleChoiceField(choices=DIAS_SEMANA, required=False),
                *(
                    forms.TimeField(
                        required=False,
                        input_formats=["%H:%M"],
                        error_messages={"invalid": "Ingrese una hora válida, por ejemplo 08:30."},
                    )
                    for _ in DIAS_SEMANA
                ),
                forms.CharField(required=False),
            ],
            require_all_fields=False,
            required=False,
            **kwargs,
        )

    def compress(self, data_list):
        datos = list(data_list) + [None] * (len(DIAS_SEMANA) + 2)
        dias = set(datos[0] or [])
        horas = dict(zip((codigo for codigo, _ in DIAS_SEMANA), datos[1:len(DIAS_SEMANA) + 1]))
        anterior = datos[len(DIAS_SEMANA) + 1]

        if not dias:
            if any(horas.values()):
                raise forms.ValidationError("Marque el día de la hora ingresada.")
            return anterior or ""

        nombres = dict(DIAS_SEMANA)
        faltan = [nombres[codigo] for codigo, _ in DIAS_SEMANA if codigo in dias and not horas[codigo]]
        if faltan:
            raise forms.ValidationError(
                "Ingrese la hora de inicio de: " + ", ".join(faltan) + "."
            )

        return texto_horario({codigo: hora for codigo, hora in horas.items() if codigo in dias})


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
                attrs={
                    "class": "form-control form-control-sm",
                    "placeholder": "Nombre oficial de la malla",
                    "title": "Escriba el nombre oficial completo, como aparece en la malla. Si aparece en la lista, selecciónelo.",
                    "autocomplete": "off",
                }
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
        self.facultad_fija = opciones.get("facultad_fija")
        self.fields["carrera_texto"].widget.choices = [("", "Seleccione"), *opciones["carreras"]]
        if self.facultad_fija:

            self.fields["facultad_texto"].widget = forms.HiddenInput()
            self.initial["facultad_texto"] = self.facultad_fija
        else:
            self.fields["facultad_texto"].widget.choices = [("", "Seleccione"), *opciones["facultades"]]

    def clean_facultad_texto(self):
        if self.facultad_fija:
            return self.facultad_fija
        return self.cleaned_data.get("facultad_texto")

    def clean_nrc(self):
        return (self.cleaned_data.get("nrc") or "").strip()


class BaseFilaPlanificacionFormSet(BaseModelFormSet):
    def __init__(self, *args, facultad=None, campus=None, **kwargs):

        kwargs.setdefault("form_kwargs", {"opciones": opciones_planificacion(facultad, campus)})
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
                    *(form.data.get(form.add_prefix(f"horario_{indice}")) for indice in range(1, len(DIAS_SEMANA) + 1)),
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

    def clean_rut(self):

        rut = (self.cleaned_data.get("rut") or "").strip()
        if not rut:
            return ""
        try:
            return validar_rut_chileno(rut)
        except ValidationError as error:
            raise forms.ValidationError(error.message)

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
    direccion = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control form-control-sm", "placeholder": "Dirección"}
        ),
    )


SocioFilaFormSet = formset_factory(
    SocioFilaForm,
    extra=0,
    can_delete=True,
)
