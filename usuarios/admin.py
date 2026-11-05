from django.contrib import admin
from .models import IdentidadInstitucional, Usuario, Rol


class IdentidadInstitucionalInline(admin.TabularInline):
    model = IdentidadInstitucional
    extra = 0
    fields = ("correo", "es_principal", "origen_vinculo", "tenant_id", "entra_oid",
              "fecha_vinculacion", "fecha_ultimo_acceso")
    readonly_fields = ("fecha_vinculacion", "fecha_ultimo_acceso")


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    search_fields = ("username", "first_name", "last_name", "correo_institucional", "identidades__correo")
    list_display = ("username", "first_name", "last_name", "correo_institucional", "activo")
    inlines = [IdentidadInstitucionalInline]


@admin.register(IdentidadInstitucional)
class IdentidadInstitucionalAdmin(admin.ModelAdmin):
    list_display = ("correo", "usuario", "es_principal", "origen_vinculo", "fecha_ultimo_acceso")
    list_filter = ("es_principal", "origen_vinculo")
    search_fields = ("correo", "usuario__username", "usuario__first_name", "usuario__last_name")


admin.site.register(Rol)
