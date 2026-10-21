from django.core.management.base import BaseCommand
from comunicaciones.models import PlantillaCorreo
from comunicaciones.services import EmailService


class Command(BaseCommand):
    help = "Ejecuta un envío de prueba utilizando el servicio de correo institucional A+S (SP6-T01 / CDE-344)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--destinatario",
            type=str,
            default="usuario.prueba@uautonoma.cl",
            help="Dirección de correo destinatario para la prueba",
        )
        parser.add_argument(
            "--plantilla",
            type=str,
            default="PRUEBA_PILOTO",
            help="Código de la plantilla de correo a utilizar",
        )

    def handle(self, *args, **options):
        destinatario = options["destinatario"]
        codigo_plantilla = options["plantilla"]

        # Crear plantilla de prueba temporal si no existe
        plantilla, _ = PlantillaCorreo.objects.get_or_create(
            codigo=codigo_plantilla,
            defaults={
                "asunto_template": "Prueba de Correo Institucional A+S - {{ fecha }}",
                "cuerpo_template": "Hola {{ nombre }},\n\nEste es un correo de prueba emitido por el servicio transversal de comunicaciones A+S.",
                "activo": True,
            },
        )

        self.stdout.write(self.style.NOTICE(f"Iniciando prueba hacia: {destinatario}"))

        envio = EmailService.enviar_correo(
            codigo_plantilla=codigo_plantilla,
            destinatario=destinatario,
            contexto={"nombre": "Usuario Prueba", "fecha": "Piloto 2026"},
        )

        if envio.resultado == "OK":
            self.stdout.write(
                self.style.SUCCESS(
                    f"Envío EXITOSO (ID: {envio.id}) | Remitente: {envio.remitente} | Reintentos: {envio.numero_intento}"
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"Envío FALLIDO (ID: {envio.id}) | Error: {envio.detalle_error}"
                )
            )