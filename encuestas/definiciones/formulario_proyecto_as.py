
from encuestas import constantes as c
from encuestas.semillas import pregunta, seccion

DEFINICION = {
    "codigo": "FORMULARIO_PROYECTO_AS_2026",
    "titulo": "Formulario del Proyecto A+S 2026",
    "proceso": "GENERAL",
    "contexto_tipo": "DOCENTE",
    "secciones": [
        seccion("Identificación del proyecto", [
            pregunta("Nombre del Proyecto A+S", c.TEXTO_CORTO),
            pregunta("Nombre de la Asignatura", c.TEXTO_CORTO),
            pregunta("Nivel", c.TEXTO_CORTO),
            pregunta("Carrera", c.TEXTO_CORTO),
            pregunta("Cantidad de Estudiantes", c.NUMERO),
            pregunta("Cantidad de grupos", c.NUMERO),
            pregunta("Nombre del docente", c.TEXTO_CORTO),
        ]),
        seccion("Resultados de aprendizaje y competencias", [
            pregunta(
                "Resultados de Aprendizaje (copiar desde el Programa)",
                c.TEXTO_LARGO,
            ),
            pregunta(
                "Competencias Genéricas (seleccione las que corresponde trabajar en su asignatura)",
                c.SELECCION_MULTIPLE,
                [
                    "Habilidades de Comunicación",
                    "Trabajo en Equipo",
                    "Comportamiento Ético",
                    "Pensamiento Crítico",
                    "Responsabilidad Social",
                ],
            ),
        ]),
        seccion("Diseño del servicio", [
            pregunta("Objetivo del Servicio", c.TEXTO_LARGO),
            pregunta("Servicio que harán los estudiantes", c.TEXTO_LARGO),
            pregunta("Posibles socios", c.TEXTO_LARGO),
        ]),
        seccion("Evaluación, reflexión y recursos", [
            pregunta(
                "Estrategia de evaluación (señale ponderaciones y tipo de evaluación)",
                c.TEXTO_LARGO,
            ),
            pregunta(
                "Estrategia de reflexión (nombre, objetivos asociados, momento en que se realizará, tiempo y recursos)",
                c.TEXTO_LARGO,
            ),
            pregunta(
                "Cierre (descripción de actividades, tiempo y producto)",
                c.TEXTO_LARGO,
            ),
            pregunta(
                "Recursos asociados (nombrar y cuantificar)",
                c.TEXTO_LARGO,
            ),
        ]),
    ],
}
