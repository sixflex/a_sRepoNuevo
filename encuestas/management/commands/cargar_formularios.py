"""
Carga en el portal los formularios que el cliente usa hoy en Microsoft Forms
(encuestas/definiciones/). Los que ya existen no se tocan, salvo con
--actualizar: entonces se crea la versión siguiente con lo nuevo de la
definición y se publica en el mismo enlace (RN-17: las versiones anteriores y
sus respuestas quedan intactas).

    python manage.py cargar_formularios                       # todos
    python manage.py cargar_formularios NUCLEO_APOYO_FISCAL   # solo algunos
    python manage.py cargar_formularios --sin-publicar        # quedan en borrador
    python manage.py cargar_formularios --actualizar EVALUACION_AS_DOCENTES
"""

from django.core.management.base import BaseCommand, CommandError

from encuestas import services
from encuestas.definiciones import DEFINICIONES, POR_CODIGO
from encuestas.semillas import actualizar_formulario, contar, crear_formulario


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
        parser.add_argument(
            "--actualizar", action="store_true",
            help="Si el formulario ya existe y su definición cambió, crea y publica la versión siguiente.",
        )

    def handle(self, *args, **options):
        desconocidos = [codigo for codigo in options["codigos"] if codigo not in POR_CODIGO]
        if desconocidos:
            raise CommandError(f"Códigos desconocidos: {', '.join(desconocidos)}. Use: {', '.join(POR_CODIGO)}.")
        definiciones = [POR_CODIGO[codigo] for codigo in options["codigos"]] or DEFINICIONES

        for definicion in definiciones:
            cargar = actualizar_formulario if options["actualizar"] else crear_formulario
            version = cargar(definicion)
            if version is None:
                motivo = "ya está al día" if options["actualizar"] else "ya existe"
                self.stdout.write(self.style.WARNING(f"«{definicion['titulo']}» {motivo}. No se cambió nada."))
                continue
            secciones, preguntas = contar(definicion)
            mensaje = (
                f"«{definicion['titulo']}» versión {version.numero_version}: "
                f"{preguntas} pregunta{'s' if preguntas != 1 else ''} "
                f"en {secciones} {'secciones' if secciones != 1 else 'sección'}."
            )
            if options["sin_publicar"]:
                self.stdout.write(self.style.SUCCESS(mensaje + " Quedó en borrador."))
                continue
            enlace = services.publicar(version)
            self.stdout.write(self.style.SUCCESS(mensaje))
            self.stdout.write(f"  Enlace público: /formularios/f/{enlace.token}/")
