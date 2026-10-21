from django.contrib import admin

from .models import (
    Evidencia,
    ExpedienteSeccion,
    RutaActividad,
    RutaPlantilla,
    RutaVersion,
    SeccionActividad,
    SeccionRuta,
)


class RutaActividadInline(admin.TabularInline):
    model = RutaActividad
    extra = 0
    fields = (
        "orden",
        "etapa",
        "nombre",
        "es_obligatoria",
        "archivo_recurso",
        "recurso_url",
        "formulario_version",
        "config_recordatorio_json",
    )
    ordering = ("orden",)


@admin.register(RutaPlantilla)
class RutaPlantillaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)


@admin.register(RutaVersion)
class RutaVersionAdmin(admin.ModelAdmin):
    list_display = (
        "plantilla",
        "numero_version",
        "estado",
        "fecha_vigencia_desde",
        "fecha_vigencia_hasta",
    )
    list_filter = ("estado", "plantilla")
    inlines = [RutaActividadInline]


@admin.register(RutaActividad)
class RutaActividadAdmin(admin.ModelAdmin):
    list_display = (
        "orden",
        "nombre",
        "etapa",
        "ruta_version",
        "es_obligatoria",
        "archivo_recurso",
        "recurso_url",
        "formulario_version",
    )
    list_filter = (
        "ruta_version",
        "etapa",
        "es_obligatoria",
    )
    list_editable = (
        "es_obligatoria",
    )
    search_fields = ("nombre", "etapa", "descripcion")
    ordering = ("ruta_version", "orden")


@admin.register(SeccionRuta)
class SeccionRutaAdmin(admin.ModelAdmin):
    list_display = (
        "seccion",
        "ruta_version",
        "estado",
        "porcentaje_final",
        "fecha_cierre",
    )
    list_filter = ("estado", "ruta_version")
    search_fields = ("seccion__nrc", "seccion__asignatura__nombre")


@admin.register(SeccionActividad)
class SeccionActividadAdmin(admin.ModelAdmin):
    list_display = (
        "seccion_ruta",
        "ruta_actividad",
        "estado",
        "completada_por_docente",
        "fecha_completada",
    )
    list_filter = ("estado", "ruta_actividad__es_obligatoria")
    search_fields = ("seccion_ruta__seccion__nrc", "ruta_actividad__nombre")


@admin.register(ExpedienteSeccion)
class ExpedienteSeccionAdmin(admin.ModelAdmin):
    list_display = ("seccion", "estado", "fecha_creacion", "fecha_cierre")
    search_fields = ("seccion__nrc",)


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "seccion_actividad",
        "archivo",
        "descripcion",
    )
    search_fields = ("archivo__nombre_original", "descripcion")
