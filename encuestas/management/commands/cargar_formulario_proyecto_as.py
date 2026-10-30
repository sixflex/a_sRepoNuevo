
from django.core.management.base import BaseCommand

from encuestas.definiciones.formulario_proyecto_as import DEFINICION
from encuestas.models import FormularioPlantilla
from encuestas.semillas import contar, crear_formulario


class Command(BaseCommand):
    help = "Carga el Formulario del Proyecto A+S 2026"

    def handle(self, *args, **options):
        version = crear_formulario(DEFINICION)

        if version is None:
            plantilla = FormularioPlantilla.objects.get(
                codigo=DEFINICION["codigo"]
            )

            self.stdout.write(
                self.style.WARNING(
                    f"El formulario ya existe (plantilla {plantilla.id}). No se realizaron cambios."
                )
            )
            return

        secciones, preguntas = contar(DEFINICION)

        self.stdout.write(
            self.style.SUCCESS(
                f"Formulario creado correctamente. "
                f"Plantilla: {version.plantilla_id}, "
                f"Versión: {version.id}, "
                f"Estado: {version.estado}, "
                f"Secciones: {secciones}, "
                f"Preguntas: {preguntas}"
            )
        )
