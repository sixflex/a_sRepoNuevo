from django.contrib import admin

from .models import (
    PlanificacionEnlace,
    Planificacion,
    FilaPlanificacion,
    FilaPlanificacionDocente,
    PlanificacionError,
)


@admin.register(PlanificacionEnlace)
class PlanificacionEnlaceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "unidad_academica",
        "campus",
        "periodo",
        "destinatario_nombre",
        "activo",
    )
    readonly_fields = ("token",)


@admin.register(Planificacion)
class PlanificacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "enlace",
        "estado",
        "filas_recibidas",
        "filas_aceptadas",
        "filas_observadas",
    )


@admin.register(FilaPlanificacion)
class FilaPlanificacionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "planificacion",
        "numero_fila",
        "nrc",
        "seccion",
        "estado_validacion",
    )


@admin.register(FilaPlanificacionDocente)
class FilaPlanificacionDocenteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fila",
        "nombre",
        "rut",
        "correo",
        "docente_resuelto",
    )


@admin.register(PlanificacionError)
class PlanificacionErrorAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "fila",
        "campo",
        "codigo",
    )