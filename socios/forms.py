from django import forms
from .models import PostulacionSocio

class PostulacionSocioForm(forms.ModelForm):
    class Meta:
        model = PostulacionSocio
        fields = ['nombre_organizacion', 'nombre_contacto', 'email_contacto', 'descripcion_proyecto']

class RechazoPostulacionForm(forms.ModelForm):
    class Meta:
        model = PostulacionSocio
        fields = ['motivo_rechazo']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['motivo_rechazo'].required = True