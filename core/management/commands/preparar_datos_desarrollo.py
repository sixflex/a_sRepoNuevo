"""
Deja una base de desarrollo lista para revisar el portal, en el orden correcto:

    1. Formularios del cliente (publicados).
    2. Formulario del Proyecto A+S y Registro de Socio Comunitario (publicados).
    3. Ruta del Docente A+S (versión activa).
    4. Plantillas de correo.
    5. Datos de demostración (docentes, secciones, equipos, socios, respuestas...).
    6. Vínculo de los dos formularios nuevos a la Ruta (queda una versión en borrador).

Cada paso se puede repetir: lo que ya existe no se duplica. Para partir de cero:

    python manage.py flush            # borra los DATOS (no las tablas); pide confirmar
    python manage.py preparar_datos_desarrollo
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from academico.models import Seccion
from encuestas import constantes as c
from encuestas import services as encuestas_services
from encuestas.definiciones.formulario_proyecto_as import DEFINICION as PROYECTO_AS
from encuestas.definiciones.registro_socio_comunitario import DEFINICION as REGISTRO_SOCIO
from encuestas.models import FormularioVersion


class Command(BaseCommand):
    help = "Carga en orden todo lo necesario para desarrollar y revisar el portal."

    def paso(self, numero, texto):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{numero}. {texto}"))

    def handle(self, *args, **options):
        self.paso(1, "Formularios del cliente")
        call_command("cargar_formularios", stdout=self.stdout)

        self.paso(2, "Formulario del Proyecto A+S y Registro de Socio Comunitario")
        call_command("cargar_formulario_proyecto_as", stdout=self.stdout)
        call_command("cargar_registro_socio_comunitario", stdout=self.stdout)
        for definicion in (PROYECTO_AS, REGISTRO_SOCIO):
            self.publicar_si_falta(definicion["codigo"])

        self.paso(3, "Ruta del Docente A+S")
        call_command("cargar_ruta_docente", stdout=self.stdout)

        self.paso(4, "Plantillas de correo")
        call_command("cargar_plantillas_correo", stdout=self.stdout)

        self.paso(5, "Datos de demostración")
        if Seccion.objects.filter(periodo__anio=2026).exists():
            self.stdout.write(self.style.WARNING(
                "Ya hay secciones de 2026: no se cargan los datos de demostración otra vez. "
                "Para partir de cero usa primero: python manage.py flush"
            ))
        else:
            try:
                call_command("cargar_datos_demo", stdout=self.stdout)
            except CommandError as error:
                self.stdout.write(self.style.WARNING(f"No se cargaron los datos de demostración: {error}"))

        self.paso(6, "Formularios nuevos en la Ruta (versión en borrador)")
        call_command("vincular_formularios_ruta", stdout=self.stdout)

        self.stdout.write(self.style.SUCCESS(
            "\nBase de desarrollo lista. Coordinador: usuario «coordinador». "
            "Docentes: su correo en «Iniciar sesión con Microsoft»."
        ))

    def publicar_si_falta(self, codigo):
        if FormularioVersion.objects.filter(plantilla__codigo=codigo, estado=c.PUBLICADA).exists():
            return
        version = (
            FormularioVersion.objects.filter(plantilla__codigo=codigo, estado=c.BORRADOR)
            .order_by("-numero_version").first()
        )
        if version:
            encuestas_services.publicar(version)
            self.stdout.write(self.style.SUCCESS(f"«{version.plantilla.titulo}» publicado."))
