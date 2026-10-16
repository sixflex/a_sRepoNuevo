from django.contrib import admin

from .models import (
    BloqueFormulario,
    EnlaceFormulario,
    FormularioPlantilla,
    FormularioVersion,
    OpcionPregunta,
    PreguntaFormulario,
    RespuestaFormulario,
)


class OpcionInline(admin.TabularInline):
    model = OpcionPregunta
    extra = 0


@admin.register(FormularioPlantilla)
class FormularioPlantillaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "codigo", "proceso", "activo")
    search_fields = ("titulo", "codigo")


@admin.register(FormularioVersion)
class FormularioVersionAdmin(admin.ModelAdmin):
    list_display = ("plantilla", "numero_version", "estado", "fecha_publicacion")
    list_filter = ("estado",)


@admin.register(BloqueFormulario)
class BloqueFormularioAdmin(admin.ModelAdmin):
    list_display = ("titulo", "formulario_version", "orden")


@admin.register(PreguntaFormulario)
class PreguntaFormularioAdmin(admin.ModelAdmin):
    list_display = ("texto", "tipo", "obligatoria", "version", "bloque", "orden")
    list_filter = ("tipo",)
    inlines = [OpcionInline]


@admin.register(EnlaceFormulario)
class EnlaceFormularioAdmin(admin.ModelAdmin):
    list_display = ("version", "token", "activo", "fecha_inicio", "fecha_expiracion")


@admin.register(RespuestaFormulario)
class RespuestaFormularioAdmin(admin.ModelAdmin):
    list_display = ("id", "version", "respondente_nombre", "respondente_rut", "carrera", "fecha_envio")
    list_filter = ("version__plantilla",)
