"""
Deja una base de desarrollo lista para revisar el portal, en el orden correcto:

    0. Comunas de Chile y clasificaciones de socio (catálogos para formularios, socios y mapa).
    1. Formularios del cliente: los que faltan se crean y los que cambiaron en
       el código pasan a una versión nueva publicada (las respuestas quedan en
       su versión).
    2. Formulario del Proyecto A+S, Acuerdo formal y Registro de Socio Comunitario (igual).
    3. Ruta del Docente A+S: si la activa no tiene las 23 actividades (p. ej. una
       Ruta de prueba hecha a mano), se crea una versión nueva y se le pasan las
       secciones sin evidencias.
    4. Plantillas de correo.
    5. Datos de demostración (si sus NRC aún no están).
    6. Vínculo del Formulario del Proyecto a la Ruta (queda una versión en borrador).
    7. Noticias A+S del portal público.

No borra nada: usuarios, secciones, respuestas y evidencias se conservan, así
que sirve para actualizar Render después de un despliegue:

    python manage.py preparar_datos_desarrollo --liviano

Para partir de cero en un PC (borra también los usuarios):

    python manage.py flush            # borra los DATOS (no las tablas); pide confirmar
    python manage.py preparar_datos_desarrollo
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from encuestas import constantes as c
from encuestas import services as encuestas_services
from encuestas.definiciones.formalizacion_acuerdos import DEFINICION as ACUERDO_FORMAL
from encuestas.definiciones.formulario_proyecto_as import DEFINICION as PROYECTO_AS
from encuestas.definiciones.registro_socio_comunitario import DEFINICION as REGISTRO_SOCIO
from encuestas.models import FormularioVersion
from encuestas.semillas import actualizar_formulario


class Command(BaseCommand):
    help = "Carga en orden todo lo necesario para desarrollar y revisar el portal."

    def add_arguments(self, parser):
        parser.add_argument(
            "--liviano", action="store_true",
            help="Datos de demostración reducidos (para Render): Ruta, formularios y panel con pocas filas.",
        )

    def paso(self, numero, texto):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{numero}. {texto}"))

    def handle(self, *args, **options):
        self.paso(0, "Comunas de Chile y clasificaciones de socio")
        call_command("cargar_catalogos_socios", stdout=self.stdout)

        self.paso(1, "Formularios del cliente")
        call_command("cargar_formularios", actualizar=True, stdout=self.stdout)

        self.paso(2, "Formulario del Proyecto A+S, Acuerdo formal y Registro de Socio Comunitario")
        for definicion in (PROYECTO_AS, ACUERDO_FORMAL, REGISTRO_SOCIO):
            version = actualizar_formulario(definicion)
            if version is None:
                self.stdout.write(f"«{definicion['titulo']}» ya está al día.")
            else:
                encuestas_services.publicar(version)
                self.stdout.write(self.style.SUCCESS(
                    f"«{definicion['titulo']}» versión {version.numero_version} publicada."
                ))
            self.publicar_si_falta(definicion["codigo"])

        self.paso(3, "Ruta del Docente A+S")
        call_command("cargar_ruta_docente", reparar=True, stdout=self.stdout)

        self.paso(4, "Plantillas de correo")
        call_command("cargar_plantillas_correo", stdout=self.stdout)

        self.paso(5, "Datos de demostración")
        # cargar_datos_demo se niega solo si sus NRC ya están; las secciones
        # creadas a mano (p. ej. en Render) no lo impiden ni se tocan.
        try:
            call_command("cargar_datos_demo", liviano=options.get("liviano", False), stdout=self.stdout)
        except CommandError as error:
            self.stdout.write(self.style.WARNING(f"No se cargaron los datos de demostración: {error}"))

        self.paso(6, "Formulario del Proyecto en la Ruta (versión en borrador)")
        try:
            call_command("vincular_formularios_ruta", stdout=self.stdout)
        except CommandError as error:
            self.stdout.write(self.style.WARNING(f"No se vinculó: {error}"))

        self.paso(7, "Noticias del portal público")
        call_command("cargar_noticias", ocultar_relleno=True, stdout=self.stdout)

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
