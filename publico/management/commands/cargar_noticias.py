"""
Noticias A+S del portal público (HU-11) para desarrollo y la demo en Render.

Carga tres noticias reales de A+S publicadas en uautonoma.cl, con su enlace,
foto y fecha. No repite una noticia que ya esté (se compara el enlace) y no
cambia las que el Coordinador haya editado u ocultado.

Con --ocultar-relleno además oculta (no borra) las noticias cuyo enlace no es
de uautonoma.cl: son pruebas cargadas a mano que llevan a páginas que no
existen.

    python manage.py cargar_noticias
    python manage.py cargar_noticias --ocultar-relleno
"""

from datetime import datetime, timezone as tz

from django.core.management.base import BaseCommand
from django.db import transaction

from publico import noticias as servicio
from publico.models import Noticia

NOTICIAS = [
    {
        "titulo": "Asesorías a emprendedores de SERCOTEC 2026",
        "resumen": (
            "Estudiantes de Ingeniería Civil Informática inician asesorías a emprendedores "
            "de SERCOTEC mediante la metodología A+S."
        ),
        "url_fuente": "https://www.uautonoma.cl/noticias/asesorias-a-emprendedores-de-sercotec",
        "imagen_url": "https://www.uautonoma.cl/content/uploads/2026/10/Asesorias.png",
        "fecha_publicacion": datetime(2026, 10, 15, 15, 0, tzinfo=tz.utc),
    },
    {
        "titulo": "Ingeniería en Control de Gestión Aprendizaje + Servicio 2026",
        "resumen": (
            "Estudiantes de Ingeniería de Control y Gestión presentaron soluciones reales para "
            "fortalecer a emprendedores mediante Aprendizaje + Servicio."
        ),
        "url_fuente": "https://www.uautonoma.cl/noticias/ingenieria-en-control-de-gestion-y-as",
        "imagen_url": "https://www.uautonoma.cl/content/uploads/2026/06/Foto-Destacada-15.png",
        "fecha_publicacion": datetime(2026, 6, 25, 16, 0, tzinfo=tz.utc),
    },
    {
        "titulo": "Tercer Seminario A+S 2025: «Co-construyendo Futuro Sostenible en el Maule»",
        "resumen": (
            "La Sede Talca reunió a docentes, estudiantes y socios comunitarios en su tercer "
            "seminario de Aprendizaje + Servicio, dedicado al desarrollo sostenible de la región."
        ),
        "url_fuente": (
            "https://www.uautonoma.cl/noticias/universidad-autonoma-de-chile-realizo-el-tercer-"
            "seminario-as-2025-co-construyendo-futuro-sostenible-en-el-maule"
        ),
        "imagen_url": "https://www.uautonoma.cl/content/uploads/2025/11/DSC_9211.jpg",
        "fecha_publicacion": datetime(2025, 11, 12, 19, 1, tzinfo=tz.utc),
    },
]


class Command(BaseCommand):
    help = "Carga tres noticias reales de A+S (uautonoma.cl) en el portal público."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ocultar-relleno", action="store_true",
            help="Oculta (no borra) las noticias cuyo enlace no es de uautonoma.cl.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        nuevas = 0
        for datos in NOTICIAS:
            url = servicio.normalizar_url(datos["url_fuente"])
            if Noticia.objects.filter(url_fuente__in=[url, url + "/"]).exists():
                continue
            Noticia.objects.create(
                **{**datos, "url_fuente": url},
                fuente=servicio.FUENTE_UA,
                estado=servicio.PUBLICADA,
            )
            nuevas += 1
        self.stdout.write(self.style.SUCCESS(
            f"Noticias: {nuevas} nuevas, {len(NOTICIAS) - nuevas} ya estaban."
        ))

        if options.get("ocultar_relleno"):
            relleno = [
                n.pk for n in Noticia.objects.filter(estado=servicio.PUBLICADA)
                if not servicio.es_leible(n.url_fuente)
            ]
            Noticia.objects.filter(pk__in=relleno).update(estado=servicio.OCULTA)
            if relleno:
                self.stdout.write(f"Se ocultaron {len(relleno)} noticias con enlaces que no son de uautonoma.cl.")
