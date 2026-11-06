
from encuestas import constantes as c
from encuestas.semillas import pregunta, seccion

DEFINICION = {
    "codigo": "FORMALIZACION_ACUERDOS_AS_2026",
    "titulo": "Formalización de Acuerdos entre Socio Comunitario y Socio Académico",
    "proceso": "GENERAL",
    "contexto_tipo": "DOCENTE",
    "secciones": [
        seccion("Identificación de los participantes", [
            pregunta("Nombre del Docente / Profesor formador", c.TEXTO_CORTO),
            pregunta("Nombre de la Asignatura", c.TEXTO_CORTO),
            pregunta("Nombre del Socio Comunitario o representante", c.TEXTO_CORTO),
            pregunta("Cargo del representante", c.TEXTO_CORTO),
            pregunta("Teléfono del representante", c.TEXTO_CORTO),
            pregunta("Correo electrónico del representante", c.CORREO),
        ]),

        seccion("Servicio y/o productos entregables", [
            pregunta(
                "Servicio y/o productos entregables que realizarán los estudiantes",
                c.TEXTO_LARGO,
            ),
        ]),

        seccion("Compromisos de los participantes", [
            pregunta(
                "Compromisos de los estudiantes (enumerar)",
                c.TEXTO_LARGO,
            ),
            pregunta(
                "Compromisos del profesor formador (enumerar)",
                c.TEXTO_LARGO,
            ),
            pregunta(
                "Compromisos del socio comunitario (enumerar)",
                c.TEXTO_LARGO,
            ),
        ]),

        seccion("Formalización del acuerdo", [
            pregunta("Nombre del docente firmante", c.TEXTO_CORTO),
            pregunta("Nombre del socio comunitario firmante", c.TEXTO_CORTO),
            pregunta("Nombre del Director/a de Carrera", c.TEXTO_CORTO),
            pregunta("Nombres de los estudiantes firmantes", c.TEXTO_LARGO),
            pregunta("Fecha del acuerdo (DD/MM/AAAA)", c.TEXTO_CORTO),
        ]),
    ],
}
