import os
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from historicos.models import CargaHistorica, CargaFila, CargaMapeo, CargaError

User = get_user_model()


class Command(BaseCommand):
    help = "Comando base para carga e ingesta de formularios históricos A+S (DE-01 / CDE-325)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--tipo",
            type=str,
            required=True,
            choices=[
                "CARTAS_PRESENTACION",
                "RESUMEN_DOCENTE",
                "REGISTRO_SOCIOS",
                "EMPRENDEDORES_FAN",
                "EVAL_ESTUDIANTES_2026",
                "EVAL_SOCIOS_2026",
                "EVAL_DOCENTES_2026",
                "CONSULTORIA_ICI",
                "PROCESOS_NEGOCIOS",
            ],
            help="Tipo de formulario histórico a cargar",
        )
        parser.add_argument(
            "--ruta",
            type=str,
            required=False,
            help="Ruta al archivo Excel (.xlsx) o CSV a procesar",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ejecuta la validación de mapeo sin persistir en la base de datos",
        )

    def handle(self, *args, **options):
        tipo_origen = options["tipo"]
        ruta_archivo = options.get("ruta")
        dry_run = options.get("dry_run", False)

        self.stdout.write(
            self.style.NOTICE(f"Iniciando verificación para tipo de origen: {tipo_origen}")
        )

        if not ruta_archivo or not os.path.exists(ruta_archivo):
            self.stdout.write(
                self.style.WARNING(
                    f"No se proporcionó archivo existente o se encuentra pendiente de recepción.\n"
                    f"Registrando verificación de estructura para: {tipo_origen}."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Archivo listo para procesar: {ruta_archivo} (dry_run={dry_run})")
        )