from django import forms

from core.validators import validar_rut_chileno

from .models import ClasificacionSocio, Comuna, SocioComunitario

# RF-SC-04 CA2: después de revisar los datos, el coordinador decide si el
# socio propuesto por un equipo queda disponible para otros grupos (sale del
# modo provisional) o solo en el historial del equipo (sigue provisional y no
# aparece en el catálogo del docente).
DECISION_HABILITAR = "habilitar"
DECISION_SOLO_EQUIPO = "solo_equipo"
DECISIONES_PROPUESTO = [
    (DECISION_HABILITAR, "Disponible para otros grupos"),
    (DECISION_SOLO_EQUIPO, "Solo en el historial del equipo"),
]


class SocioPropuestoForm(forms.ModelForm):
    """Datos del socio que propuso un equipo, para que el coordinador los corrija."""

    contacto_nombre = forms.CharField(label="Nombre del contacto", max_length=180, required=False)
    contacto_cargo = forms.CharField(label="Cargo", max_length=120, required=False)
    contacto_correo = forms.EmailField(label="Correo", required=False)
    contacto_telefono = forms.CharField(
        label="Teléfono", max_length=30, required=False,
        widget=forms.TextInput(attrs={"placeholder": "+56912345678"}),
    )
    decision = forms.ChoiceField(
        label="Decisión", choices=DECISIONES_PROPUESTO, required=False, widget=forms.RadioSelect,
    )

    class Meta:
        model = SocioComunitario
        fields = [
            "nombre_organizacion",
            "rut",
            "clasificacion",
            "clasificacion_otra",
            "comuna",
            "direccion_exacta",
            "centro_servicio",
        ]
        labels = {
            "nombre_organizacion": "Nombre de la organización",
            "rut": "RUT",
            "clasificacion": "Clasificación",
            "clasificacion_otra": "Otra clasificación",
            "comuna": "Comuna",
            "direccion_exacta": "Dirección",
            "centro_servicio": "Centro de servicio (SERCOTEC u otro)",
        }
        widgets = {
            "rut": forms.TextInput(attrs={"placeholder": "12345678-5"}),
        }
        help_texts = {
            "rut": "Opcional. Sin puntos y con guion.",
            "clasificacion_otra": "Solo si no corresponde a ninguna de la lista.",
        }

    def __init__(self, *args, contacto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.contacto = contacto
        if contacto and not self.is_bound:
            self.initial.update({
                "contacto_nombre": contacto.nombre,
                "contacto_cargo": contacto.cargo,
                "contacto_correo": contacto.correo,
                "contacto_telefono": contacto.telefono,
            })
        self.fields["clasificacion"].queryset = ClasificacionSocio.objects.filter(activo=True)
        self.fields["clasificacion"].empty_label = "Seleccione"
        self.fields["comuna"].queryset = Comuna.objects.filter(activo=True).order_by("nombre")
        self.fields["comuna"].empty_label = "Seleccione"
        for nombre, campo in self.fields.items():
            if nombre == "decision":
                continue
            clase = "form-select" if isinstance(campo.widget, forms.Select) else "form-control"
            campo.widget.attrs.setdefault("class", clase)

    def clean_rut(self):
        rut = (self.cleaned_data.get("rut") or "").strip()
        if not rut:
            return None
        rut = validar_rut_chileno(rut)
        if SocioComunitario.objects.filter(rut=rut).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ya existe otro socio con este RUT.")
        return rut

    def clean(self):
        datos = super().clean()
        contacto = [datos.get(f"contacto_{campo}") for campo in ("cargo", "correo", "telefono")]
        if any(contacto) and not datos.get("contacto_nombre"):
            self.add_error("contacto_nombre", "Indica el nombre del contacto.")
        return datos
