"""
Formularios del Núcleo de Apoyo Fiscal (forms del cliente): el registro de
cada atención y la encuesta de satisfacción de la Operación Renta.
"""

from encuestas import constantes as c
from encuestas.semillas import otras, pregunta, seccion

NUCLEO_APOYO_FISCAL = {
    "codigo": "NUCLEO_APOYO_FISCAL",
    "titulo": "Núcleo Apoyo Fiscal Universidad Autónoma de Chile",
    "proceso": "NUCLEO_APOYO_FISCAL",
    "contexto_tipo": "ATENCION",
    "secciones": [
        seccion("Atención", [
            pregunta("Selecciones su local de atención", c.ALTERNATIVA_UNICA, [
                'Universidad Autónoma Providencia (Pedro de Valdivia 425, Providencia)',
                'Universidad Autónoma El Llano (Ramón Subercaseaux 1404, San Miguel)',
                'HUB Providencia ( Los Jesuitas, Los Jesuitas 881, Providencia)',
            ]),
            pregunta("Nombre y Apellido del Estudiante que atendió", c.TEXTO_CORTO),
            pregunta("RUT del Estudiante que atendió (Sin puntos y con guión)", c.RUT),
        ]),
        seccion("Contribuyente", [
            pregunta("Nombre del Contribuyente", c.TEXTO_CORTO, dato_respondente="nombre"),
            pregunta("Apellidos del Contribuyente", c.TEXTO_CORTO),
            pregunta("RUT (Sin puntos y con guión)", c.RUT, dato_respondente="rut"),
            pregunta("Email", c.CORREO, obligatoria=False, dato_respondente="correo"),
            pregunta("Télefono de contacto", c.TEXTO_CORTO, ayuda="Ejemplo: +56 9 1234 5678"),
            pregunta("Dirección", c.TEXTO_CORTO),
            pregunta("Comuna", c.ALTERNATIVA_UNICA, [
                'Providencia',
                'San Miguel',
                'Otra',
            ]),
        ]),
        seccion("Consulta", [
            pregunta("Tipo de Atención", c.ALTERNATIVA_UNICA, [
                'Como Persona Natural',
                'A nombre de una Institución',
                otras(),
            ]),
            pregunta("Motivo de su consulta", c.SELECCION_MULTIPLE, [
                'Formalización',
                'Tasaciones esporádicas y Microempresas familiares',
                'Documentos Tributarios Electrónicos',
                'Impuesto al Valor Agregado  (IVA)',
                'Término de Giro',
                otras(),
            ]),
            pregunta("Se solucionó la consulta?", c.ALTERNATIVA_UNICA, [
                'Si',
                'No',
                'El contribuyente quedo citado para una próxima oportunidad',
                otras(),
            ]),
        ]),
    ],
}

SATISFACCION_OPERACION_RENTA = {
    "codigo": "SATISFACCION_OPERACION_RENTA",
    "titulo": "Encuesta de Satisfacción Operación Renta 2026 - Universidad Autónoma de Chile",
    "descripcion": (
        "Estimado(a),\n"
        "En línea con nuestro espíritu de constante autoevaluación, sus observaciones nos ayudan a promover la "
        "mejora continua y mantener los estándares de calidad que hemos comprometido con nuestra comunidad "
        "universitaria y con el entorno en que estamos insertos."
    ),
    "proceso": "OPERACION_RENTA",
    "contexto_tipo": "PARTICIPANTE",
    "secciones": [
        seccion("Sobre usted", [
            pregunta("¿Cómo se enteró de la actividad?", c.SELECCION_MULTIPLE, [
                'Servicio de Impuestos Internos - SII',
                'E-mail',
                'Sitio web UA',
                'Redes Sociales',
                'Docentes',
                'Prensa',
                otras(),
            ]),
            pregunta("Identificación del participante", c.ALTERNATIVA_UNICA, [
                'Contribuyente 2da categoría',
                'Comunidad/Vecino/Entorno',
                'Estudiante UA',
                'Titulado UA',
                'Estudiante otra casa de estudios',
                'Directivo de Organización Pública',
                'Directivo de Institución Privada',
                'Funcionario',
                'Docente',
                otras(),
            ]),
            pregunta("¿En qué campus de la Universidad Autónoma fue atendido?", c.ALTERNATIVA_UNICA, [
                'Campus San Miguel',
                'Campus Providencia',
            ]),
        ]),
        seccion("Evaluación de la actividad", [
            pregunta(
                "¿Considera que la actividad realizada mejora su conocimiento sobre el proceso de declaración "
                "de renta y el cumplimiento de sus obligaciones tributarias?",
                c.ESCALA,
            ),
            pregunta(
                "¿Considera que esta actividad formativa promueve mejoras en las acciones de la comunidad, "
                "haciéndolas más eficientes y perdurables en el tiempo, fomentando la responsabilidad social?",
                c.ESCALA,
            ),
            pregunta(
                "¿Considera que su participación en esta actividad contribuye al mejoramiento de su bienestar, "
                "salud o calidad de vida?",
                c.ESCALA,
            ),
            pregunta("El estudiante que lo atendió resolvió a cabalidad su requerimiento", c.ESCALA),
            pregunta("¿La actividad aportó a su requerimiento?", c.ESCALA),
            pregunta("¿Volvería a participar en actividades similares con la Universidad?", c.ESCALA),
            pregunta("Nombre del Alumno que realizó la atención", c.TEXTO_CORTO, obligatoria=False),
            pregunta("Sugerencias o comentarios", c.TEXTO_LARGO, obligatoria=False),
            pregunta("¿Cuál es su nivel de satisfacción general con la actividad?", c.ESCALA),
        ]),
    ],
}
