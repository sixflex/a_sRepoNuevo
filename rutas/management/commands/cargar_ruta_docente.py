from datetime import date

from django.core.management.base import BaseCommand
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
    help = "Carga la Ruta del Docente A+S 2026"

    def handle(self, *args, **options):
        plantilla, _ = RutaPlantilla.objects.get_or_create(
            nombre="Ruta del Docente A+S",
            defaults={
                "descripcion": "Ruta del Docente A+S 2026 - Sede Santiago",
                "activo": True,
            },
        )

        version, _ = RutaVersion.objects.get_or_create(
            plantilla=plantilla,
            numero_version=1,
            defaults={
                "estado": "ACTIVA",
                "fecha_vigencia_desde": date(2026, 1, 1),
            },
        )

        # Orden y contenido según la Ruta docente entregada por Coordinación
        # (knowledge/Ruta docente.txt). Todas obligatorias por indicación del
        # cliente mientras se valida PV-03.
        actividades = [
            (1, "Inicio y habilitación", "Completar curso habilitante en metodología A+S",
             "Completar el curso de metodología A+S disponible en Canvas durante las primeras tres semanas."),
            (2, "Inicio y habilitación", "Coordinar reunión inicial con Coordinación A+S",
             "Contactar al Coordinador A+S para agendar una visita a la sala, revisar el uso de formatos y recibir las instrucciones del período."),
            (3, "Inicio y habilitación", "Presentar la metodología A+S al curso",
             "Explicar a los estudiantes en qué consiste el trabajo A+S, con la opción de invitar al Coordinador a una charla presencial."),
            (4, "Inicio y habilitación", "Definir Socio Comunitario",
             "Establecer junto a los estudiantes con qué Socio Comunitario se trabajará, cómo se realizará el primer contacto y quién lo gestionará."),
            (5, "Inicio y habilitación", "Completar Formulario del Proyecto",
             "Identificar las Competencias Genéricas involucradas según el programa de la asignatura y completar el Formulario del Proyecto."),
            (6, "Diseño del proyecto", "Seleccionar Socios Comunitarios",
             "Elegir junto a Coordinación los Socios Comunitarios pertinentes. Se puede solicitar una reunión presencial en la Universidad para explicarles la metodología y los tiempos."),
            (7, "Diseño del proyecto", "Identificar necesidades",
             "Detectar junto al Socio Comunitario y los estudiantes una necesidad real que permita trabajar los Resultados de Aprendizaje y las Competencias Genéricas."),
            (8, "Diseño del proyecto", "Definir el servicio",
             "Acordar en conjunto las acciones, compromisos, fechas y duración del trabajo."),
            (9, "Diseño del proyecto", "Construir instrumento de evaluación",
             "Diseñar la pauta institucional con las ponderaciones: Resultados de Aprendizaje 50%, servicio 30%, reflexión 10% y Competencias Genéricas 10%."),
            (10, "Diseño del proyecto", "Solicitar Carta de Presentación",
             "Si los estudiantes necesitan acreditar que pertenecen a la Universidad y trabajan bajo supervisión, solicitar la carta a Coordinación."),
            (11, "Formalización", "Firmar el Acuerdo Formal",
             "Oficializar el trabajo entre el Socio Comunitario, la asignatura y los estudiantes con un acuerdo firmado antes de ejecutar el servicio, y subirlo como evidencia."),
            (12, "Formalización", "Realizar primera actividad de reflexión",
             "Realizar la primera actividad de reflexión antes de iniciar el trabajo en terreno, para preparar a los estudiantes y vincular el servicio con la asignatura."),
            (13, "Formalización", "Registrar Socio Comunitario",
             "Un estudiante por grupo registra con qué Socio Comunitario trabajará el equipo."),
            (14, "Implementación", "Ejecutar el servicio",
             "Llevar a cabo el trabajo planificado en terreno junto a los estudiantes y el Socio Comunitario."),
            (15, "Implementación", "Realizar segunda actividad de reflexión",
             "Desarrollar la segunda actividad de reflexión cuando los grupos ya estén interactuando activamente con el Socio Comunitario."),
            (16, "Implementación", "Recopilar evidencias",
             "Reunir fotografías, productos y otros respaldos durante todo el proceso."),
            (17, "Cierre y reporte", "Realizar tercera actividad de reflexión",
             "Ejecutar la última actividad de reflexión de la asignatura."),
            (18, "Cierre y reporte", "Organizar el evento de cierre",
             "Invitar a los Socios Comunitarios a la Universidad para la presentación final de informes y trabajos. Se pueden reservar salas o pedir apoyo a Coordinación."),
            (19, "Cierre y reporte", "Aplicar encuestas de satisfacción",
             "Proyectar el código QR en una de las últimas clases para que estudiantes, Socios Comunitarios y docentes respondan las encuestas."),
            (20, "Cierre y reporte", "Completar evaluación y planilla de notas",
             "Completar el instrumento de evaluación y la planilla de calificaciones final."),
            (21, "Cierre y reporte", "Informar métricas académicas",
             "Informar el promedio A+S, el promedio final del curso, el número de reprobados y el porcentaje de reprobación."),
            (22, "Cierre y reporte", "Enviar documentación final",
             "Subir las evidencias recopiladas, la planilla de notas y el acuerdo firmado."),
            (23, "Cierre y reporte", "Completar Formulario Resumen",
             "Completar el Formulario Resumen del proyecto antes de cerrar el proceso de reporte."),
        ]

        # Acción o formulario de cada actividad (RF-RUT-01). recurso_url admite
        # {seccion} y {actividad}; se editan desde el admin sin tocar código.
        recursos = {
            10: {"recurso_url": _url_con_marcador("cartas:solicitar_carta_docente", "{seccion}")},
            13: {"recurso_url": _url_con_marcador("socios:asociar_socio_equipo", "{actividad}")},
            # Actividad de cierre: pregunta si habrá cierre e invita al Socio (RF-EVI-04, RF-RUT-04).
            18: {"config_recordatorio_json": {"recordatorio": RECORDATORIO_INVITACION_CIERRE}},
            19: {"recurso_url": reverse("rutas:formularios_qr") + "?proceso=EVALUACION_AS"},
            23: {"formulario_version": _ultima_version("RESUMEN_IMPLEMENTACION_DOCENTE")},
        }

        creadas = 0
        actualizadas = 0

        for orden, etapa, nombre, descripcion in actividades:
            _, creada = RutaActividad.objects.update_or_create(
                ruta_version=version,
                orden=orden,
                defaults={
                    "etapa": etapa,
                    "nombre": nombre,
                    "descripcion": descripcion,
                    "es_obligatoria": True,
                    "formulario_version": None,
                    "recurso_url": None,
                    "config_recordatorio_json": None,
                    **recursos.get(orden, {}),
                },
            )

            if creada:
                creadas += 1
            else:
                actualizadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Ruta del Docente A+S cargada correctamente. "
                f"Actividades creadas: {creadas}. "
                f"Actividades actualizadas: {actualizadas}. "
                f"Total: {len(actividades)}."
            )
        )