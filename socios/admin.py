from django.contrib import admin
from .models import (
    ClasificacionSocio,
    Comuna,
    ParticipacionSocio,
    PostulacionSocio,
    SocioComunitario,
)

admin.site.register(Comuna)
admin.site.register(ClasificacionSocio)
admin.site.register(SocioComunitario)
admin.site.register(ParticipacionSocio)
admin.site.register(PostulacionSocio)
