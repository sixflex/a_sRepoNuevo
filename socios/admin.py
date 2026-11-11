from django.contrib import admin
from .models import (
    ClasificacionSocio,
    Comuna,
    Convocatoria,
    ParticipacionSocio,
    PostulacionSocio,
    SocioComunitario,
)

admin.site.register(Comuna)
admin.site.register(ClasificacionSocio)
admin.site.register(SocioComunitario)
admin.site.register(ParticipacionSocio)
admin.site.register(PostulacionSocio)


@admin.register(Convocatoria)
class ConvocatoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "estado", "fecha_inicio", "fecha_fin", "formulario_version")
    list_filter = ("estado", "fecha_inicio", "fecha_fin")
    search_fields = ("nombre",)