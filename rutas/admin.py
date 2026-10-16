from django.contrib import admin

from .models import RutaActividad, RutaPlantilla, RutaVersion


class RutaActividadInline(admin.TabularInline):
    model = RutaActividad
    extra = 0
    ordering = ("orden",)
    fields = (
        "orden",
        "etapa",
        "nombre",
        "es_obligatoria",
        "formulario_version",
        "archivo_recurso",
        "recurso_url",
        "config_recordatorio_json",
    )


@admin.register(RutaPlantilla)
class RutaPlantillaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")


@admin.register(RutaVersion)
class RutaVersionAdmin(admin.ModelAdmin):
    list_display = ("plantilla", "numero_version", "estado")
    inlines = [RutaActividadInline]


@admin.register(RutaActividad)
class RutaActividadAdmin(admin.ModelAdmin):
    list_display = ("orden", "nombre", "etapa", "es_obligatoria", "ruta_version")
    list_editable = ("es_obligatoria",)
    list_filter = ("ruta_version", "etapa", "es_obligatoria")
    ordering = ("ruta_version", "orden")
    search_fields = ("nombre",)
