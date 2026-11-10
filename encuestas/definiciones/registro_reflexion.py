"""
Registro de reflexión A+S (actividades 12, 15 y 17 de la Ruta del Docente).

Sigue la pauta de sistematización del documento «Actividades de reflexión
A+S» de la Ruta: el docente indica cuál de las dinámicas sugeridas para ese
momento hizo (u otra), cuándo y cómo, qué se reflexionó y adjunta un respaldo.
"""

from encuestas import constantes as c
from encuestas.semillas import opcion, otras, pregunta, seccion

CODIGO = "REGISTRO_REFLEXION_AS"

ANTES = "ANTES"
DURANTE = "DURANTE"
DESPUES = "DESPUES"

# Momento -> dinámicas sugeridas en el documento de la Ruta.
DINAMICAS = {
    ANTES: [
        "Jenga: propuestas de mejora y competencias",
        "¿Cómo me enfrento a los conflictos?",
        "Me reconozco como agente de cambio",
    ],
    DURANTE: [
        "Análisis de nuestro primer encuentro",
        "Mesa redonda",
        "Identifico mis metas",
    ],
    DESPUES: [
        "Jenga: aprendizajes adquiridos",
        "Dados mágicos",
        "Quemada de síntesis",
    ],
}

# Orden de la actividad en la Ruta -> momento de la reflexión.
MOMENTO_POR_ORDEN = {12: ANTES, 15: DURANTE, 17: DESPUES}


def _dinamicas():
    opciones = []
    for momento, nombres in DINAMICAS.items():
        opciones += [opcion(nombre, solo_si=("momento", [momento])) for nombre in nombres]
    return opciones + [otras("Otra dinámica")]


DEFINICION = {
    "codigo": CODIGO,
    "titulo": "Registro de actividad de reflexión A+S",
    "descripcion": (
        "Registra la actividad de reflexión que hiciste con tus estudiantes. "
        "Puedes usar una de las dinámicas sugeridas o una propia."
    ),
    "proceso": "GENERAL",
    "contexto_tipo": "DOCENTE",
    "secciones": [
        seccion("Actividad de reflexión", [
            pregunta("¿Qué reflexión estás registrando?", c.ALTERNATIVA_UNICA, [
                opcion("Primera: antes del servicio", valor=ANTES),
                opcion("Segunda: durante el servicio", valor=DURANTE),
                opcion("Tercera: después del servicio", valor=DESPUES),
            ], clave="momento"),
            pregunta("¿Qué dinámica realizaste?", c.ALTERNATIVA_UNICA, _dinamicas(),
                     ayuda="Las dinámicas sugeridas están en el documento «Actividades de reflexión A+S» de la Ruta."),
            pregunta("Fecha de la actividad", c.FECHA),
            pregunta("Modalidad", c.ALTERNATIVA_UNICA, ["Presencial", "Online", "Mixta"]),
            pregunta("¿Cómo se trabajó?", c.ALTERNATIVA_UNICA, ["Individual", "Grupal", "Mixta"]),
            pregunta("Describe brevemente la reflexión desarrollada", c.TEXTO_LARGO,
                     ayuda="Qué se conversó, qué aprendizajes o compromisos surgieron."),
            pregunta("Respaldo de la actividad (opcional)", c.ARCHIVO, obligatoria=False,
                     ayuda="Una foto, la pauta usada o el producto de la dinámica."),
        ]),
    ],
}
