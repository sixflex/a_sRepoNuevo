from django import forms
from django.forms import modelformset_factory
from .models import PlanificacionAS

class PlanificacionASForm(forms.ModelForm):
    class Meta:
        model = PlanificacionAS
        exclude = ['carrera', 'token_acceso', 'estado_registro']
        widgets = {
            'nrc': forms.TextInput(attrs={'class': 'form-control'}),
            'seccion': forms.TextInput(attrs={'class': 'form-control'}),
            'nivel': forms.TextInput(attrs={'class': 'form-control'}),
            'horario': forms.TextInput(attrs={'class': 'form-control'}),
            'estudiantes_planificados': forms.NumberInput(attrs={'class': 'form-control'}),
            'campus': forms.Select(attrs={'class': 'form-select'}),
            'asignatura': forms.Select(attrs={'class': 'form-select'}),
            'docente': forms.Select(attrs={'class': 'form-select'}),
            'declaracion_as': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

PlanificacionASFormSet = modelformset_factory(
    PlanificacionAS,
    form=PlanificacionASForm,
    extra=1,
    can_delete=True
)