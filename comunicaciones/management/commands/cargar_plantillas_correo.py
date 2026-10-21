"""
Carga las plantillas de correo del portal. Las que ya existen no se tocan,
así se conservan los cambios hechos por Coordinación desde el admin.

    python manage.py cargar_plantillas_correo
"""

from django.core.management.base import BaseCommand

from comunicaciones.models import PlantillaCorreo


PLANTILLAS = [
    {
        # RF-CAR-07: el mensaje pide al Docente comprobar la carta antes de entregarla.
        "codigo": "CARTA_PRESENTACION_DOCENTE",
        "asunto_template": "Carta de Presentación aprobada - Solicitud #{{ numero_solicitud }}",
        "cuerpo_template": (
            "{% autoescape off %}"
            "Estimado/a {{ docente }}:\n\n"
            "Coordinación A+S aprobó la Carta de Presentación dirigida a {{ persona_receptora }} "
            "({{ institucion }}) para la asignatura {{ asignatura }} (NRC {{ nrc }}). "
            "La encontrará adjunta en PDF.\n\n"
            "Antes de entregarla a sus estudiantes, compruebe que los datos de la carta sean correctos. "
            "Si encuentra un error, avise a Coordinación A+S antes de distribuirla.\n\n"
            "Coordinación Aprendizaje + Servicio\n"
            "Universidad Autónoma de Chile"
            "{% endautoescape %}"
        ),
    },
]


class Command(BaseCommand):
    help = "Carga las plantillas de correo del portal (RF-COM-01)."

    def handle(self, *args, **options):
        for plantilla in PLANTILLAS:
            _, creada = PlantillaCorreo.objects.get_or_create(
                codigo=plantilla["codigo"],
                defaults={
                    "asunto_template": plantilla["asunto_template"],
                    "cuerpo_template": plantilla["cuerpo_template"],
                    "activo": True,
                },
            )
            if creada:
                self.stdout.write(self.style.SUCCESS(f"Plantilla {plantilla['codigo']} creada."))
            else:
                self.stdout.write(self.style.WARNING(f"Plantilla {plantilla['codigo']} ya existe. No se cambió nada."))
