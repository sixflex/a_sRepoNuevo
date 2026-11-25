
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.urls import reverse

from encuestas.models import FormularioVersion
from rutas.models import Evidencia, RutaActividad, RutaPlantilla, RutaVersion, SeccionRuta
from rutas.services import RECORDATORIO_INVITACION_CIERRE, asignar_ruta_a_seccion, obtener_version_ruta_vigente


def _url_con_marcador(nombre_url, marcador):
    return reverse(nombre_url, args=[0]).replace("/0/", f"/{marcador}/")


def _ultima_version(codigo_plantilla):
    return (
        FormularioVersion.objects
        .filter(plantilla__codigo=codigo_plantilla)
        .order_by("-numero_version")
        .first()
    )



TOTAL_ACTIVIDADES = 23


class Command(BaseCommand):
    help = "Carga la Ruta del Docente A+S 2026 según PV-03"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reparar", action="store_true",
            help=(
                "Si la Ruta activa no tiene las 23 actividades (p. ej. una Ruta de prueba hecha "
                "a mano), crea una versión nueva con las 23, la deja activa y pasa a ella las "
                "secciones sin evidencias subidas. No borra usuarios ni respuestas."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        plantilla, _ = RutaPlantilla.objects.get_or_create(
            nombre="Ruta del Docente A+S",
            defaults={
                "descripcion": "Ruta del Docente A+S 2026 - Sede Santiago",
                "activo": True,
            },
        )

        if not plantilla.versiones.exists():
            version = RutaVersion.objects.create(
                plantilla=plantilla, numero_version=1, estado="BORRADOR",
                fecha_vigencia_desde=date(2026, 1, 1),
            )
            self.cargar_version(version)
            if options.get("reparar"):

                self.mover_secciones(version)
            return

        vigente = obtener_version_ruta_vigente()
        total = vigente.actividades.count() if vigente else 0
        if total == TOTAL_ACTIVIDADES:
            self.stdout.write(self.style.SUCCESS(
                f"La versión {vigente.numero_version} ya tiene las {TOTAL_ACTIVIDADES} actividades. "
                "Se conserva sin modificaciones."
            ))
            return


        if not options.get("reparar"):
            self.stdout.write(self.style.WARNING(
                f"Ojo: la Ruta activa tiene {total} actividades y la Ruta del Docente tiene "
                f"{TOTAL_ACTIVIDADES}. Para corregirla sin borrar datos usa: "
                "python manage.py cargar_ruta_docente --reparar"
            ))
            return

        siguiente = (plantilla.versiones.order_by("-numero_version").first().numero_version) + 1
        nueva = RutaVersion.objects.create(
            plantilla=plantilla, numero_version=siguiente, estado="BORRADOR",
            fecha_vigencia_desde=date(2026, 1, 1),
        )
        plantilla.versiones.filter(estado="ACTIVA").update(estado="INACTIVA")
        self.cargar_version(nueva)
        self.mover_secciones(nueva)

    def cargar_version(self, version):
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
            5: {
                "formulario_version": _ultima_version(
                    "FORMULARIO_PROYECTO_AS_2026"
                ),
            },
            23: {
                "formulario_version": _ultima_version(
                    "RESUMEN_IMPLEMENTACION_DOCENTE"
                ),
            },
        }

        recursos.setdefault(1, {})["recurso_url"] = "https://canvas.uautonoma.cl"


        opcionales = {10, 18}

        nuevas_actividades = [
            RutaActividad(
                ruta_version=version,
                orden=orden,
                etapa=etapa,
                nombre=nombre,
                descripcion=descripcion,
                es_obligatoria=orden not in opcionales,
                **recursos.get(orden, {}),
            )
            for orden, etapa, nombre, descripcion in actividades
        ]

        RutaActividad.objects.bulk_create(nuevas_actividades)

        version.estado = "ACTIVA"
        version.save(update_fields=["estado"])

        self.stdout.write(
            self.style.SUCCESS(
                "Ruta del Docente A+S cargada correctamente. "
                f"Versión: {version.numero_version}. "
                f"Actividades creadas: {len(nuevas_actividades)}."
            )
        )

    def mover_secciones(self, nueva):
        """
        Pasa a la Ruta nueva las secciones que estaban en una versión
        incompleta. Lo marcado como hecho se conserva cuando la actividad
        tiene el mismo número y nombre; las secciones con evidencias subidas
        se dejan como están (las evidencias no se borran).
        """
        movidas, con_evidencias = 0, []
        for seccion_ruta in (
            SeccionRuta.objects.exclude(ruta_version=nueva)
            .select_related("seccion", "ruta_version")
        ):
            if seccion_ruta.ruta_version.actividades.count() == TOTAL_ACTIVIDADES:
                continue
            if Evidencia.objects.filter(seccion_actividad__seccion_ruta=seccion_ruta).exists():
                con_evidencias.append(seccion_ruta.seccion.nrc)
                continue
            hechas = {
                (a.ruta_actividad.orden, a.ruta_actividad.nombre): a
                for a in seccion_ruta.actividades.select_related("ruta_actividad").exclude(fecha_completada=None)
            }
            seccion_ruta.actividades.all().delete()
            seccion_ruta.ruta_version = nueva
            seccion_ruta.estado = "EN_PROGRESO"
            seccion_ruta.save(update_fields=["ruta_version", "estado"])
            asignar_ruta_a_seccion(seccion_ruta.seccion, nueva)
            for actividad in seccion_ruta.actividades.select_related("ruta_actividad"):
                anterior = hechas.get((actividad.ruta_actividad.orden, actividad.ruta_actividad.nombre))
                if anterior:
                    actividad.estado = anterior.estado
                    actividad.fecha_completada = anterior.fecha_completada
                    actividad.completada_por_docente = anterior.completada_por_docente
                    actividad.observacion = anterior.observacion
                    actividad.save()
            completadas = seccion_ruta.actividades.filter(
                ruta_actividad__es_obligatoria=True, completada_por_docente__isnull=False,
            ).count()
            obligatorias = seccion_ruta.actividades.filter(ruta_actividad__es_obligatoria=True).count()
            seccion_ruta.porcentaje_final = round(Decimal(completadas) * 100 / obligatorias, 2) if obligatorias else Decimal("0.00")
            seccion_ruta.save(update_fields=["porcentaje_final"])
            movidas += 1

        self.stdout.write(self.style.SUCCESS(f"Secciones pasadas a la versión {nueva.numero_version}: {movidas}."))
        if con_evidencias:
            self.stdout.write(self.style.WARNING(
                "Se dejaron en su versión anterior por tener evidencias subidas: "
                + ", ".join(f"NRC {nrc}" for nrc in con_evidencias)
            ))
