
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from encuestas.models import FormularioVersion
from rutas.models import RutaActividad, RutaVersion
from rutas.services import crear_nueva_version_ruta, obtener_version_ruta_vigente


FORMULARIOS = {
    5: "FORMULARIO_PROYECTO_AS_2026",
    13: "REGISTRO_SOCIO_COMUNITARIO_AS_2026",
}


class Command(BaseCommand):
    help = (
        "Vincula los formularios de las actividades 5 y 13 a la versión en borrador "
        "de la Ruta Docente; si no hay borrador, lo crea desde la versión activa"
    )

    @transaction.atomic
    def handle(self, *args, **options):
        # Se usa el borrador más reciente, no "la versión 2": los números de
        # versión dependen de cada base de datos.
        ruta = (
            RutaVersion.objects.select_for_update()
            .filter(
                plantilla__nombre="Ruta del Docente A+S",
                estado="BORRADOR",
            )
            .order_by("-numero_version")
            .first()
        )

        if ruta is None:
            vigente = obtener_version_ruta_vigente()

            if vigente is None:
                raise CommandError(
                    "No existe una versión activa de la Ruta del Docente A+S. "
                    "Ejecuta primero: python manage.py cargar_ruta_docente"
                )

            # Si algo falla más abajo, la transacción deshace también este borrador.
            ruta = crear_nueva_version_ruta(vigente)
            cambios = [
                f"Se creó la versión {ruta.numero_version} en borrador "
                f"a partir de la versión {vigente.numero_version}"
            ]
        else:
            cambios = []

        for orden, codigo in FORMULARIOS.items():
            actividades = list(
                RutaActividad.objects.select_for_update().filter(
                    ruta_version=ruta,
                    orden=orden,
                )
            )

            if len(actividades) != 1:
                raise CommandError(
                    f"Se esperaba una actividad de orden {orden} en la versión {ruta.numero_version}."
                )

            versiones = list(
                FormularioVersion.objects.filter(
                    plantilla__codigo=codigo,
                    estado="PUBLICADA",
                ).order_by("-numero_version", "-pk")[:2]
            )

            if not versiones:
                raise CommandError(
                    f"No existe una versión publicada del formulario {codigo}. "
                    "Cárgalo y publícalo desde el editor de formularios antes de vincularlo."
                )

            if len(versiones) > 1 and versiones[0].numero_version == versiones[1].numero_version:
                raise CommandError(
                    f"Existen versiones publicadas ambiguas para {codigo}."
                )

            actividad = actividades[0]
            formulario = versiones[0]

            if actividad.formulario_version_id not in (None, formulario.pk):
                raise CommandError(
                    f"La actividad {orden} ya tiene otro formulario vinculado."
                )

            if actividad.formulario_version_id == formulario.pk:
                cambios.append(f"Actividad {orden}: ya estaba vinculada")
                continue

            actividad.formulario_version = formulario
            actividad.save(update_fields=["formulario_version"])
            cambios.append(f"Actividad {orden}: vinculada correctamente")

        for cambio in cambios:
            self.stdout.write(self.style.SUCCESS(cambio))

        self.stdout.write(
            self.style.SUCCESS(
                f"Integración completada en la versión {ruta.numero_version} (borrador). "
                "La versión activa no fue modificada."
            )
        )
