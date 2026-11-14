from django import forms
from django.core.exceptions import ValidationError

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
                .con_socio_vigente()
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

        # Opciones para no escribir todo a mano: el equipo se muestra por su
        # grupo y su socio, y la institución sugiere los socios de la sección
        # con su contacto principal. Sigue siendo texto libre porque la carta
        # puede ir a otra institución (reunión con el cliente 10-11-2026).
        self.fields["equipo"].label_from_instance = _nombre_equipo
        self.fields["equipo"].empty_label = "Sin equipo (carta general)"
        self.fields["institucion_receptora"].widget.attrs.update(
            {"list": "sugerencias-institucion", "autocomplete": "off",
             "placeholder": "Escribe o elige un socio de la sección"}
        )
        self.fields["persona_receptora"].widget.attrs.setdefault("placeholder", "Ej: María Pérez")
        self.fields["cargo_receptor"].widget.attrs.setdefault("placeholder", "Ej: Directora")
        self.fields["institucion_receptora"].help_text = "Al elegir un socio se completan la persona y el cargo con su contacto principal."
        self.sugerencias = sugerencias_receptor(seccion) if seccion is not None else []
        self.socio_por_equipo = {
            str(equipo.pk): equipo.socio_vigente.nombre_organizacion
            for equipo in self.fields["equipo"].queryset
            if equipo.socio_vigente
        } if seccion is not None else {}

    def clean_equipo(self):
        equipo = self.cleaned_data.get("equipo")
        
        if equipo:
            cantidad = equipo.integrantes.count() 
            if cantidad > 6:
                raise ValidationError(
                    f"El equipo seleccionado tiene {cantidad} estudiantes. Las cartas están limitadas a un máximo de 6 estudiantes por equipo."
                )
                
        return equipo


def _nombre_equipo(equipo):
    socio = equipo.socio_vigente
    return f"Grupo {equipo.numero_grupo}" + (f" · {socio.nombre_organizacion}" if socio else " · sin socio")


def sugerencias_receptor(seccion):
    """
    Socios de la sección (los de sus equipos y los que eligió el docente)
    con el nombre y cargo de su contacto principal.
    """
    from socios.models import ContactoSocio, SocioComunitario
    from socios.services import socios_elegidos_seccion

    ids = set(socios_elegidos_seccion(seccion).values_list("id", flat=True))
    ids |= {e.socio_vigente.pk for e in seccion.equipos.con_socio_vigente() if e.socio_vigente}
    contactos = {}
    for contacto in (
        ContactoSocio.objects.filter(socio_id__in=ids, activo=True)
        .order_by("-es_principal", "id")
    ):
        contactos.setdefault(contacto.socio_id, contacto)
    return [
        {
            "institucion": socio.nombre_organizacion,
            "persona": contactos[socio.pk].nombre if socio.pk in contactos else "",
            "cargo": (contactos[socio.pk].cargo or "") if socio.pk in contactos else "",
        }
        for socio in SocioComunitario.objects.filter(pk__in=ids).order_by("nombre_organizacion")
    ]
