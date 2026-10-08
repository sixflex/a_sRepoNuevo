"""
Carga solo la Ficha de Inscripción de Emprendedores (encuestas/definiciones/
ficha_emprendedores.py). Equivale a `cargar_formularios FICHA_EMPRENDEDORES`.

    python manage.py cargar_ficha_emprendedores [--sin-publicar]
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Carga la Ficha de Inscripción de Emprendedores con pestañas por programa (HU-09)."

    def add_arguments(self, parser):
        parser.add_argument("--sin-publicar", action="store_true", help="Deja el formulario en borrador.")

    def handle(self, *args, **options):
        call_command(
            "cargar_formularios", "FICHA_EMPRENDEDORES",
            sin_publicar=options["sin_publicar"], stdout=self.stdout,
        )
