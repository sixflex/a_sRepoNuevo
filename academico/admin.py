from django.contrib import admin

from .models import (
    Sede,
    Campus,
    Facultad,
    Carrera,
    Asignatura,
    AsignaturaCarrera,
    Docente,
    PeriodoAcademico,
    Seccion,
    SeccionCarrera,
    SeccionDocente,
)


admin.site.register(Sede)
admin.site.register(Campus)
admin.site.register(Facultad)
admin.site.register(Carrera)
admin.site.register(Asignatura)
admin.site.register(AsignaturaCarrera)
admin.site.register(Docente)
admin.site.register(PeriodoAcademico)
admin.site.register(Seccion)
admin.site.register(SeccionCarrera)
admin.site.register(SeccionDocente)