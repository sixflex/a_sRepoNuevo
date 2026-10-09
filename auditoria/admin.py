from django.contrib import admin
from .models import AuditoriaCambio


@admin.register(AuditoriaCambio)
class AuditoriaCambioAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "actor_externo", "entidad", "entidad_id", "accion", "ip")
    list_filter = ("accion", "entidad", "fecha")
    search_fields = ("entidad", "entidad_id", "usuario__username", "actor_externo")
    ordering = ("-fecha",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False