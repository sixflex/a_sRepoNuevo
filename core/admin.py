from django.contrib import admin
from .models import Sede, Campus, Anio, PeriodoAcademico, Carrera, Asignatura, Seccion, Docente

# Registramos todos los modelos para que aparezcan en el panel de administración
admin.site.register(Sede)
admin.site.register(Campus)
admin.site.register(Anio)
admin.site.register(PeriodoAcademico)
admin.site.register(Carrera)
admin.site.register(Asignatura)
admin.site.register(Seccion)
admin.site.register(Docente)