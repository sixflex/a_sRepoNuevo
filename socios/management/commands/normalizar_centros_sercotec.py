"""
Lleva el Centro de Negocios SERCOTEC de cada socio al nombre oficial de la
lista (socios/centros_sercotec.py), para poder agrupar por centro.

Por defecto solo muestra qué cambiaría; con --aplicar guarda los cambios.
Los textos que no se reconocen se listan y no se tocan.

    python manage.py normalizar_centros_sercotec
    python manage.py normalizar_centros_sercotec --aplicar
"""

from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction

from auditoria.services import registrar_auditoria
from socios.centros_sercotec import normalizar_centro
from socios.models import SocioComunitario


class Command(BaseCommand):
    help = "Normaliza el Centro de Negocios SERCOTEC de los socios comunitarios."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Guarda los cambios (sin esto, solo los muestra).")

    def handle(self, *args, **options):
        cambios = []
        sin_reconocer = Counter()

        socios = SocioComunitario.objects.exclude(centro_servicio__isnull=True).exclude(centro_servicio="")
        for socio in socios.order_by("pk"):
            oficial = normalizar_centro(socio.centro_servicio)
            if oficial is None:
                sin_reconocer[socio.centro_servicio] += 1
            elif oficial != socio.centro_servicio:
                cambios.append((socio, socio.centro_servicio, oficial))

        for socio, anterior, oficial in cambios:
            self.stdout.write(f"  {socio.nombre_organizacion}: «{anterior}» → «{oficial}»")
        if sin_reconocer:
            self.stdout.write(self.style.WARNING("Sin reconocer (no se tocan; agrégalos a la lista si corresponde):"))
            for texto, cantidad in sin_reconocer.most_common():
                self.stdout.write(f"  «{texto}» ({cantidad})")

        if not options["aplicar"]:
            self.stdout.write(self.style.SUCCESS(
                f"{len(cambios)} socio(s) por normalizar. Ejecuta con --aplicar para guardar."
            ))
            return

        with transaction.atomic():
            for socio, anterior, oficial in cambios:
                socio.centro_servicio = oficial
                socio.save(update_fields=["centro_servicio"])
                registrar_auditoria(
                    entidad="SocioComunitario",
                    entidad_id=socio.pk,
                    accion="NORMALIZAR_CENTRO_SERCOTEC",
                    valores_anteriores={"centro_servicio": anterior},
                    valores_nuevos={"centro_servicio": oficial},
                    actor_externo="normalizar_centros_sercotec",
                )
        self.stdout.write(self.style.SUCCESS(f"{len(cambios)} socio(s) normalizado(s)."))
