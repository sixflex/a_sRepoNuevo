from django.contrib import admin
from comunicaciones.models import EnvioCorreo, PlantillaCorreo
from comunicaciones.services import EmailService


@admin.register(PlantillaCorreo)
class PlantillaCorreoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "asunto_template", "activo")
    search_fields = ("codigo", "asunto_template")
    list_filter = ("activo",)


@admin.register(EnvioCorreo)
class EnvioCorreoAdmin(admin.ModelAdmin):
    list_display = (
        "destinatario",
        "asunto",
        "resultado",
        "fecha_envio",
        "numero_intento",
        "plantilla",
    )
    list_filter = ("resultado", "fecha_envio")
    search_fields = ("destinatario", "asunto", "remitente")
    readonly_fields = ("fecha_envio", "numero_intento", "detalle_error")
    actions = ["reintentar_correos_fallidos"]

    @admin.action(description="Reintentar envíos seleccionados")
    def reintentar_correos_fallidos(self, request, queryset):
        for envio in queryset:
            EmailService.reintentar_envio(envio.id)
        self.message_user(request, "Proceso de reintento ejecutado.")