
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse

from encuestas.models import FormularioVersion
from rutas.models import RutaActividad, RutaPlantilla, RutaVersion
from rutas.services import RECORDATORIO_INVITACION_CIERRE


def _url_con_marcador(nombre_url, marcador):
    return reverse(nombre_url, args=[0]).replace("/0/", f"/{marcador}/")


def _ultima_version(codigo_plantilla):
    return (
        FormularioVersion.objects
        .filter(plantilla__codigo=codigo_plantilla)
        .order_by("-numero_version")
        .first()
    )


class Command(BaseCommand):
    help = "Carga la Ruta del Docente A+S 2026 según PV-03"

    @transaction.atomic
    def handle(self, *args, **options):
        plantilla, _ = RutaPlantilla.objects.get_or_create(
            nombre="Ruta del Docente A+S",
            defaults={
                "descripcion": "Ruta del Docente A+S 2026 - Sede Santiago",
                "activo": True,
            },
        )

        version, version_creada = RutaVersion.objects.get_or_create(
            plantilla=plantilla,
            numero_version=1,
            defaults={
                "estado": "BORRADOR",
                "fecha_vigencia_desde": date(2026, 1, 1),
            },
        )

        if not version_creada:
            self.stdout.write(
                self.style.SUCCESS(
                    "La versión 1 ya existe. Se conserva sin modificaciones."
                )
            )
            return
        actividades = [
            (
                1,
                "Inicio y habilitación",
                "Completar curso habilitante en metodología A+S",
                "Completar el curso habilitante en metodología A+S disponible en Canvas.",
                True,
                False,
                "https://canvas.uautonoma.cl",
            ),
            (
                2,
                "Inicio y habilitación",
                "Coordinar reunión con Coordinación A+S",
                "Coordinar una reunión con el Coordinador A+S para revisar instrumentos, formatos e instrucciones.",
                True,
                False,
                None,
            ),
            (
                3,
                "Inicio y habilitación",
                "Explicar la metodología A+S al curso",
                "Explicar al curso la metodología A+S e invitar al Coordinador A+S a una charla presencial.",
                True,
                False,
                None,
            ),
            (
                4,
                "Inicio y habilitación",
                "Definir Socio Comunitario",
                "Definir con estudiantes y Coordinación el Socio Comunitario y cómo se gestionará el primer contacto.",
                True,
                False,
                None,
            ),
            (
                5,
                "Inicio y habilitación",
                "Completar Formulario del Proyecto",
                "Identificar las Competencias Genéricas involucradas y completar el Formulario del Proyecto.",
                True,
                False,
                None,
            ),
            (
                6,
                "Diseño del proyecto",
                "Seleccionar Socios Comunitarios",
                "Seleccionar con Coordinación uno o más Socios Comunitarios pertinentes para la asignatura.",
                True,
                False,
                None,
            ),
            (
                7,
                "Diseño del proyecto",
                "Identificar necesidad real y sentida",
                "Identificar con estudiantes y Socio Comunitario una necesidad real y sentida vinculada a los Resultados de Aprendizaje y Competencias Genéricas.",
                True,
                False,
                None,
            ),
            (
                8,
                "Diseño del proyecto",
                "Definir servicio, compromisos, fechas y duración",
                "Definir el servicio, los compromisos de las partes, las fechas y la duración del trabajo.",
                True,
                False,
                None,
            ),
            (
                9,
                "Diseño del proyecto",
                "Construir instrumento de evaluación",
                "Construir el instrumento de evaluación institucional considerando Resultados de Aprendizaje, reflexión, Competencias Genéricas y servicio.",
                True,
                False,
                None,
            ),
            (
                10,
                "Diseño del proyecto",
                "Solicitar Carta Formal de Presentación",
                "Solicitar, cuando sea necesario, una Carta Formal de Presentación para presentar a los estudiantes ante el Socio Comunitario.",
                False,
                False,
                None,
            ),
            (
                11,
                "Formalización",
                "Formalizar acuerdo",
                "Formalizar el acuerdo entre el Socio Comunitario, la asignatura y los grupos antes del servicio y entregar el acuerdo firmado como evidencia.",
                True,
                True,
                None,
            ),
            (
                12,
                "Formalización",
                "Realizar primera actividad de reflexión",
                "Realizar la primera actividad de reflexión antes del inicio del servicio.",
                True,
                False,
                None,
            ),
            (
                13,
                "Formalización",
                "Registrar Socio Comunitario",
                "Un estudiante por grupo completa, bajo supervisión del docente, el registro del Socio Comunitario.",
                True,
                False,
                None,
            ),
            (
                14,
                "Implementación",
                "Realizar servicio planificado",
                "Realizar el servicio planificado junto con los estudiantes y el Socio Comunitario.",
                True,
                False,
                None,
            ),
            (
                15,
                "Implementación",
                "Realizar segunda actividad de reflexión",
                "Desarrollar la segunda actividad de reflexión durante el trabajo con el Socio Comunitario.",
                True,
                False,
                None,
            ),
            (
                16,
                "Implementación",
                "Recopilar evidencias",
                "Recopilar fotografías, videos, productos y otras evidencias del trabajo realizado.",
                True,
                True,
                None,
            ),
            (
                17,
                "Cierre y reporte",
                "Coordinar cierre del proyecto",
                "Coordinar el cierre del proyecto con los Socios Comunitarios y la presentación de los informes o trabajos realizados.",
                False,
                False,
                None,
            ),
            (
                18,
                "Cierre y reporte",
                "Realizar tercera actividad de reflexión",
                "Desarrollar la tercera actividad de reflexión.",
                True,
                False,
                None,
            ),
            (
                19,
                "Cierre y reporte",
                "Gestionar encuestas A+S",
                "Gestionar las encuestas A+S de estudiantes, docente y Socios Comunitarios.",
                True,
                False,
                None,
            ),
            (
                20,
                "Cierre y reporte",
                "Completar evaluación y planilla de notas",
                "Completar el instrumento de evaluación y la planilla de notas.",
                True,
                True,
                None,
            ),
            (
                21,
                "Cierre y reporte",
                "Enviar evidencias y documentación",
                "Enviar a Coordinación las evidencias, la planilla de notas y el acuerdo firmado.",
                True,
                True,
                None,
            ),
            (
                22,
                "Cierre y reporte",
                "Informar resultados académicos",
                "Informar el promedio A+S, promedio final del curso, número de estudiantes reprobados y porcentaje de reprobación.",
                True,
                False,
                None,
            ),
            (
                23,
                "Cierre y reporte",
                "Completar Formulario Resumen",
                "Completar el Formulario Resumen del proyecto antes del cierre del proceso de reporte.",
                True,
                False,
                None,
            ),
        ]
        recursos = {
            10: {
                "recurso_url": _url_con_marcador(
                    "cartas:solicitar_carta_docente",
                    "{seccion}",
                ),
            },
            13: {
                "recurso_url": _url_con_marcador(
                    "socios:asociar_socio_equipo",
                    "{actividad}",
                ),
            },
            18: {
                "config_recordatorio_json": {
                    "recordatorio": RECORDATORIO_INVITACION_CIERRE,
                },
            },
            19: {
                "recurso_url": (
                    reverse("rutas:formularios_qr")
                    + "?proceso=EVALUACION_AS"
                ),
            },
            23: {
                "formulario_version": _ultima_version(
                    "RESUMEN_IMPLEMENTACION_DOCENTE"
                ),
            },
        }

        creadas = 0
        actualizadas = 0

        for orden, etapa, nombre, descripcion, es_obligatoria, acepta_evidencias, recurso_url in actividades:
            _, creada = RutaActividad.objects.update_or_create(
                ruta_version=version,
                orden=orden,
                defaults={
                    "etapa": etapa,
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "es_obligatoria": es_obligatoria,
                    "acepta_evidencias": acepta_evidencias,
                    "recurso_url": recurso_url,
                },
            )
            for orden, etapa, nombre, descripcion in actividades
        ]

        RutaActividad.objects.bulk_create(nuevas_actividades)

        version.estado = "ACTIVA"
        version.save(update_fields=["estado"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Ruta del Docente A+S cargada correctamente según PV-03. "
                f"Actividades creadas: {creadas}. "
                f"Actividades actualizadas: {actualizadas}. "
                f"Total: {len(actividades)}."
            )
        )
