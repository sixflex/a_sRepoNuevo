"""
Trabajo del equipo con su socio (preguntas 17 a 22 del Registro de Socios
Comunitarios de la Coordinación).

El año y el semestre salen del período de la sección; los beneficiarios, el
servicio realizado, la evaluación del socio (1 a 5 estrellas) y el
comentario los completa el equipo durante el semestre desde el mismo enlace
del registro. Quedan en la participación vigente del equipo
(ParticipacionSocio), que es la fuente única del socio del equipo; por eso
los puede completar o corregir cualquier integrante, aunque cambie quien
registró el equipo.
"""

from django import forms

from auditoria.services import registrar_auditoria

CAMPOS = ("beneficiarios_estimados", "servicio_realizado", "evaluacion", "comentario")


class TrabajoSocioForm(forms.Form):
    beneficiarios_estimados = forms.IntegerField(
        label="Número de beneficiarios (personas) que se llegó a favorecer con el proyecto (aproximado)",
        min_value=0, max_value=1000000, required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "inputmode": "numeric", "placeholder": "Ej: 40"}),
    )
    servicio_realizado = forms.CharField(
        label="¿En qué consistió el servicio realizado al socio? (no más de tres líneas)",
        max_length=600, required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    evaluacion = forms.TypedChoiceField(
        label="Evalúe al socio (¿lo recomendaría para volver a trabajar con él?)",
        choices=[(str(n), str(n)) for n in range(1, 6)], coerce=int, empty_value=None, required=False,
        widget=forms.RadioSelect,
    )
    comentario = forms.CharField(
        label="Comentario acerca del socio",
        max_length=1000, required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    def clean_servicio_realizado(self):
        return " ".join(self.cleaned_data["servicio_realizado"].split())

    def clean_comentario(self):
        return " ".join(self.cleaned_data["comentario"].split())


def formulario(participacion, datos=None):
    inicial = {campo: getattr(participacion, campo) for campo in CAMPOS} if participacion else {}
    if inicial.get("evaluacion") is not None:
        inicial["evaluacion"] = str(inicial["evaluacion"])
    return TrabajoSocioForm(datos, initial=inicial)


def completo(participacion):
    """El equipo ya contó su trabajo con el socio (todas las preguntas respondidas)."""
    return bool(participacion) and all(
        getattr(participacion, campo) not in (None, "") for campo in CAMPOS
    )


def guardar(participacion, form, request):
    anteriores = {campo: getattr(participacion, campo) for campo in CAMPOS}
    for campo in CAMPOS:
        valor = form.cleaned_data.get(campo)
        setattr(participacion, campo, valor if valor not in ("",) else None)
    participacion.save(update_fields=list(CAMPOS))
    registrar_auditoria(
        request=request,
        entidad="ParticipacionSocio",
        entidad_id=participacion.pk,
        accion="COMPLETAR_TRABAJO_SOCIO",
        valores_anteriores=anteriores,
        valores_nuevos={campo: getattr(participacion, campo) for campo in CAMPOS},
    )
