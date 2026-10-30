
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from encuestas import constantes as c
from encuestas.definiciones.registro_socio_comunitario import DEFINICION
from encuestas.models import FormularioPlantilla, FormularioVersion
from encuestas.semillas import _crear_contenido, contar


class Command(BaseCommand):
    help = "Carga el registro de socios en la versión borrador 8 ya existente"

    @transaction.atomic
    def handle(self, *args, **options):
        plantilla = FormularioPlantilla.objects.select_for_update().filter(pk=8).first()

        if plantilla is None or plantilla.titulo != DEFINICION["titulo"]:
            raise CommandError(
                "La plantilla 8 no corresponde al Registro de Socio Comunitario A+S 2026"
            )

        version = FormularioVersion.objects.select_for_update().filter(
            pk=8,
            plantilla=plantilla
        ).first()

        if version is None or version.estado != c.BORRADOR:
            raise CommandError(
                "La versión 8 no existe o ya no está en borrador"
            )

        if version.preguntas.exists() or version.respuestas.exists() or version.enlaces.exists():
            raise CommandError(
                "La versión 8 ya contiene preguntas, respuestas o enlaces; no se modificó"
            )

        if plantilla.versiones.exclude(pk=8).exists():
            raise CommandError(
                "La plantilla tiene otras versiones; se requiere revisión manual"
            )

        if FormularioPlantilla.objects.exclude(pk=8).filter(
            codigo=DEFINICION["codigo"]
        ).exists():
            raise CommandError(
                "El código de formulario ya existe en otra plantilla"
            )

        bloques = list(version.bloques.all())

        if len(bloques) > 1 or any(b.preguntas.exists() for b in bloques):
            raise CommandError(
                "La estructura existente no está vacía; no se modificó"
            )

        version.bloques.all().delete()

        plantilla.codigo = DEFINICION["codigo"]
        plantilla.save(update_fields=["codigo"])

        version.contexto_tipo = DEFINICION["contexto_tipo"]
        version.save(update_fields=["contexto_tipo"])

        _crear_contenido(version, DEFINICION)

        secciones, preguntas = contar(DEFINICION)

        self.stdout.write(
            self.style.SUCCESS(
                f"Formulario 8, versión 8: {secciones} secciones y {preguntas} preguntas cargadas"
            )
        )
