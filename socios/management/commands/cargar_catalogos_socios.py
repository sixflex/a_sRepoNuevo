from django.core.management.base import BaseCommand
from django.db import transaction

from socios.comunas import cargar_catalogo
from socios.constantes import CLASIFICACIONES_SOCIO
from socios.models import ClasificacionSocio


class Command(BaseCommand):
    help = (
        "Carga las 346 comunas de Chile (con región y ubicación para el mapa) y las "
        "clasificaciones de socio del Registro de Socios Comunitarios. Se puede repetir."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        creadas, completadas = cargar_catalogo()
        self.stdout.write(self.style.SUCCESS(
            f"Comunas listas: {creadas} nuevas, {completadas} completadas con región o ubicación."
        ))
        nuevas = 0
        for nombre in CLASIFICACIONES_SOCIO:
            if not ClasificacionSocio.objects.filter(nombre__iexact=nombre).exists():
                ClasificacionSocio.objects.create(nombre=nombre, activo=True)
                nuevas += 1
        self.stdout.write(self.style.SUCCESS(f"Clasificaciones de socio listas: {nuevas} nuevas."))
