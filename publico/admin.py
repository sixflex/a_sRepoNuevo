from django.contrib import admin

from .models import Noticia


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "fuente", "fecha_publicacion", "estado", "fecha_sincronizacion")
    list_filter = ("estado",)
    search_fields = ("titulo", "resumen", "url_fuente")
