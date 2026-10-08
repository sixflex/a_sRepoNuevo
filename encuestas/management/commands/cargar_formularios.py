"""
Carga en el portal los formularios que el cliente usa hoy en Microsoft Forms
(encuestas/definiciones/). Los que ya existen no se tocan.

    python manage.py cargar_formularios                       # todos
    python manage.py cargar_formularios NUCLEO_APOYO_FISCAL   # solo algunos
    python manage.py cargar_formularios --sin-publicar        # quedan en borrador
"""

from django.core.management.base import BaseCommand, CommandError

from encuestas import services
from encuestas.definiciones import DEFINICIONES, POR_CODIGO
from encuestas.semillas import contar, crear_formulario


class Command(BaseCommand):
    help = "Carga los formularios del cliente como formularios configurables (HU-09)."

    def add_arguments(self, parser):
        parser.add_argument(
            "codigos", nargs="*",
            help=f"Códigos a cargar (por defecto, todos): {', '.join(POR_CODIGO)}.",
        )
        parser.add_argument(
            "--sin-publicar", action="store_true",
            help="Deja los formularios en borrador en vez de publicarlos.",
        )

    def handle(self, *args, **options):
        desconocidos = [codigo for codigo in options["codigos"] if codigo not in POR_CODIGO]
        if desconocidos:
            raise CommandError(f"Códigos desconocidos: {', '.join(desconocidos)}. Use: {', '.join(POR_CODIGO)}.")
        definiciones = [POR_CODIGO[codigo] for codigo in options["codigos"]] or DEFINICIONES

        for definicion in definiciones:
            version = crear_formulario(definicion)
            if version is None:
                self.stdout.write(self.style.WARNING(f"«{definicion['titulo']}» ya existe. No se cambió nada."))
                continue
            secciones, preguntas = contar(definicion)
            mensaje = (
                f"«{definicion['titulo']}» creado: {preguntas} pregunta{'s' if preguntas != 1 else ''} "
                f"en {secciones} {'secciones' if secciones != 1 else 'sección'}."
            )
            if options["sin_publicar"]:
                self.stdout.write(self.style.SUCCESS(mensaje + " Quedó en borrador."))
                continue
            enlace = services.publicar(version)
            self.stdout.write(self.style.SUCCESS(mensaje))
            self.stdout.write(f"  Enlace público: /formularios/f/{enlace.token}/")
