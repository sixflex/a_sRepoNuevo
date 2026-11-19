"""
Marca un campus en las carreras activas que todavía no tienen ninguno
(CarreraCampus). Sirve para dejar lista una base existente después de la
migración 0005; las carreras que ya tienen campus no se tocan.

    python manage.py asignar_campus_carreras --campus "Campus Providencia"
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academico.models import Campus, Carrera, CarreraCampus


class Command(BaseCommand):
    help = "Asigna un campus a las carreras activas que no tienen ninguno."

    def add_arguments(self, parser):
        parser.add_argument("--campus", required=True, help='Nombre del campus, p. ej. "Campus Providencia".')

    def handle(self, *args, **options):
        nombre = options["campus"].strip()
        coincidencias = list(Campus.objects.filter(nombre__iexact=nombre, activo=True).select_related("sede"))
        if not coincidencias:
            raise CommandError(f'No existe un campus activo llamado "{nombre}".')
        if len(coincidencias) > 1:
            raise CommandError(f'Hay {len(coincidencias)} campus llamados "{nombre}" en distintas sedes.')
        campus = coincidencias[0]

        carreras = list(Carrera.objects.filter(activo=True, campus__isnull=True).order_by("nombre"))
        with transaction.atomic():
            CarreraCampus.objects.bulk_create(
                [CarreraCampus(carrera=carrera, campus=campus) for carrera in carreras]
            )
        self.stdout.write(self.style.SUCCESS(
            f"{len(carreras)} carrera(s) quedaron impartidas en {campus.sede.nombre} · {campus.nombre}."
        ))
