from django.contrib import admin
from core.models import Noticia


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "fuente", "url_fuente", "fecha_publicacion", "estado")
    list_filter = ("estado", "fecha_publicacion")
    search_fields = ("titulo", "resumen", "fuente", "url_fuente")

# Los modelos académicos se administran desde academico/admin.py.
# Core no registra modelos propios actualmente.