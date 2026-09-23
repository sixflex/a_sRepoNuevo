from django.contrib import admin
from .models import PlanificacionAS

@admin.register(PlanificacionAS)
class PlanificacionASAdmin(admin.ModelAdmin):
    list_display = ('nrc', 'asignatura', 'carrera', 'estado_registro', 'token_acceso')
    readonly_fields = ('token_acceso',)