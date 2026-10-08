"""
Encuestas de Evaluación A+S 2026 para estudiantes, Socios Comunitarios y
docentes (forms del cliente).

El txt del cliente solo trae las preguntas de identificación de estas tres
encuestas; las preguntas de evaluación se agregan desde el constructor.
"""

from encuestas import constantes as c
from encuestas.semillas import pregunta, seccion

ESTUDIANTES = {
    "codigo": "EVALUACION_AS_ESTUDIANTES",
    "titulo": "Encuesta de Evaluación A+S Estudiantes 2026",
    "descripcion": (
        "Te invitamos a responder la encuesta considerando la experiencia que tuviste durante el semestre "
        "aprendiendo con A+S en esta asignatura. Es importante que respondas con sinceridad y comentes lo que "
        "sea necesario, tus respuestas ayudarán a mejorar futuras versiones de la asignatura. La información "
        "que entregues será usada para análisis de la asignatura y para análisis institucional, los resultados "
        "serán comunicados, pero nunca se identificará a los estudiantes que responden, se resguardará siempre "
        "el anonimato de las respuestas."
    ),
    "proceso": "EVALUACION_AS",
    "contexto_tipo": "ESTUDIANTE",
    "secciones": [
        seccion("Identificación", [
            pregunta("Rut (sin puntos y con guión  XXXXXXXXX-Y)", c.RUT, dato_respondente="rut"),
            pregunta("Facultad", c.LISTA, [
                'ADMINISTRACIÓN Y NEGOCIOS',
                'ARQUITECTURA, CONSTRUCCIÓN Y MEDIO AMBIENTE',
                'CIENCIAS DE LA SALUD',
                'CIENCIAS SOCIALES Y HUMANIDADES',
                'DERECHO',
                'EDUCACIÓN',
                'INGENIERIA',
                'FORMACION GENERAL',
            ]),
            pregunta("Selecciona el Campus o Sede donde cursaste la asignatura", c.ALTERNATIVA_UNICA, [
                'Santiago Campus El Llano',
                'Santiago Campus Providencia',
                'Sede Talca',
                'Sede Temuco',
            ]),
            pregunta("Carrera", c.LISTA, [
                'Formación General',
                'Administración Pública',
                'Arquitectura',
                'Ingeniería en Control de Gestión',
                'Derecho',
                'Enfermería',
                'Fonoaudiología',
                'Ingeniería Civil Industrial',
                'Ingeniería Civil Informática',
                'Ingeniería Civil Química',
                'Ingeniería Comercial',
                'Ingeniería en Administración',
                'Ingeniería en Construcción',
                'Kinesiología',
                'Licenciatura en Artes Visuales',
                'Medicina',
                'Nutrición y Dietética',
                'Obstetricia y Puericultura',
                'Odontología',
                'Pedagogía en Educación Básica',
                'Pedagogía en Educación Diferencial',
                'Pedagogía en Educación Física',
                'Pedagogía en Educación Parvularia',
                'Pedagogía en Historia Geografía y Cs. Sociales',
                'Pedagogía en Inglés',
                'Pedagogía en Lengua Castellana y Comunicación',
                'Relaciones Públicas',
                'Periodismo',
                'Psicología',
                'Publicidad y Comunicación Integral',
                'Química y Farmacia',
                'Terapia Ocupacional',
                'Trabajo Social',
            ]),
            pregunta("Semestre", c.ALTERNATIVA_UNICA, [
                'Otoño',
                'Primavera',
            ], clave="semestre"),
        ]),
        seccion("Asignatura A+S", [
            pregunta(
                "Asignaturas A+S  que cursaste en  Semestre Otoño (Selecciona la que corresponde a tu carrera "
                "o la que corresponde al electivo de Formación General)",
                c.LISTA,
                [
                    'RESPONSABILIDAD SOCIAL E INNOVACIÓN SOCIAL',
                    'EMPRENDIMIENTOS COMUNITARIOS',
                    'ALIMENTACIÓN COMUNITARIA SUSTENTABLE',
                    'CLÍNICA JURÍDICA',
                    'EDUCACIÓN EN ENFERMERÍA',
                    'FARMACIA ASISTENCIAL',
                    'GESTIÓN DE ORGANIZACIONES DE LA SOCIEDAD CIVIL',
                    'GESTIÓN DE PROCESOS DE NEGOCIOS',
                    'GESTIÓN DE PROYECTOS ARTÍSTICOS',
                    'GESTIÓN DEL CUIDADO EN COMUNIDADES I',
                    'INNOVACIÓN Y EMPRENDIMIENTO',
                    'INTERVENCIÓN EN SALUD COMUNITARIA Y GESTIÓN SOCIAL',
                    'INVESTIGACIÓN DE MERCADOS',
                    'MARKETING SOCIAL',
                    'NORMATIVA TRIBUTARIA II',
                    'ORGANIZACIONES SOCIALES',
                    'PATRIMONIO Y BIENES CULTURALES',
                    'PLANIFICACIÓN DE EVENTOS CORPORATIVOS',
                    'PRÁCTICA INTERMEDIA I: VINCULACIÓN CON LA FAMILIA',
                    'PRÁCTICA INTERMEDIA III: GESTIÓN DEL APRENDIZAJE',
                    'PRÁCTICA IV',
                    'PRÁCTICA PROFESIONAL I',
                    'PRÁCTICA PROFESIONAL II',
                    'PROYECTO DE TÍTULO I',
                    'PROYECTOS SOCIALES I',
                    'PSICOMOTRICIDAD EN EL DESARROLLO INTEGRAL',
                    'SALUD COMUNITARIA Y FAMILIAR II',
                    'TALLER DE COMUNICACIÓN ESTRATÉGICA',
                    'TALLER DE PEQUEÑA EMPRESA',
                    'GESTIÓN DE PRÁCTICAS PARA LA ENSEÑANZA Y EL APRENDIZAJE I',
                    'INTERVENCIÓN SOCIOCOMUNITARIA',
                    'CLÍNICA DE MATRONERÍA COMUNITARIA Y ATENCIÓN PRIMARIA DE SALUD II (A+S)',
                    'AYUDAS TÉCNICAS Y TECNOLOGÍAS DE APOYO I',
                    'SALUD COMUNITARIA IV Medicina',
                    'OTRA',
                ],
            ),
        ], si=("semestre", ["Otoño"])),
        seccion("Asignatura A+S", [
            pregunta(
                "Asignaturas A+S que cursaste en  Semestre Primavera (Selecciona la que corresponde a tu carrera "
                "o bien al electivo de Formación General)",
                c.ALTERNATIVA_UNICA,
                [
                    'EMPRENDIMIENTOS COMUNITARIOS',
                    'RESPONSABILIDAD SOCIAL E INNOVACIÓN SOCIAL',
                    'CARDIOLOGÍA Y ODONTOLOGÍA PREVENTIVA',
                    'CLÍNICA DE MATRONERÍA COMUNITARIA Y ATENCIÓN PRIMARIA DE SALUD I',
                    'CLÍNICA JURÍDICA',
                    'CONSULTORÍA DE EMPRESAS',
                    'DESARROLLO APLICACIONES WEB',
                    'GERIATRÍA Y GERONTOLOGÍA APLICADA',
                    'GESTIÓN AMBIENTAL Y ENERGÍA',
                    'GESTIÓN DEL CUIDADO EN COMUNIDADES I',
                    'GESTIÓN SOCIAL PARA EL DESARROLLO',
                    'GOBIERNO ELECTRÓNICO Y PARTICIPACIÓN CIUDADANA',
                    'HERRAMIENTAS DIGITALES II',
                    'INTERVENCIÓN FONOAUDIOLÓGICA EN AUDICIÓN Y EQUILIBRIO II',
                    'INTERVENCIÓN PSICOEDUCATIVA EN CONTEXTO ESCOLARES',
                    'INTERVENCIÓN PSICOSOCIAL CON GRUPOS',
                    'PRÁCTICA INTERMEDIA II: GESTIÓN DE APRENDIZAJE',
                    'PRÁCTICA INTERMEDIA III: GESTIÓN DE APRENDIZAJE',
                    'PROYECTO DE TÍTULO II',
                    'REALIZACIÓN AUDIOVISUAL',
                    'SALUD COMUNITARIA Y FAMILIAR VI',
                    'TALLER DE OBRAS',
                    'TALLER INTEGRADO DE FARMACOLOGÍA',
                    'TALLER IV: CICLO INICIAL',
                    'TALLER VIII: CICLO INTERMEDIO: URBANISMO SOCIAL',
                    'EMPRENDIMIENTO E INNOVACIÓN - Arquitectura',
                    'ARQUITECTURA Y PATRIMONIO',
                    'OTRA',
                ],
            ),
        ], si=("semestre", ["Primavera"])),
    ],
}

SOCIOS_COMUNITARIOS = {
    "codigo": "EVALUACION_AS_SOCIOS",
    "titulo": "Encuesta de Evaluación Socios Comunitarios A+S 2026",
    "descripcion": (
        "Le invitamos a responder la siguiente encuesta considerando su experiencia con Aprendizaje más "
        "Servicio. Le pedimos responder con toda sinceridad y comentar todo lo que considere necesario, ya que "
        "sus respuestas ayudarán a mejorar el trabajo a futuro. La información será utilizada para análisis de "
        "la asignatura y para análisis institucional, los resultados serán comunicados, pero no se identificará "
        "a las personas que responden, se resguardará siempre el anonimato de sus respuestas.\n\n"
        "Responderla le tomará solo unos minutos.\n\nMuchas gracias."
    ),
    "proceso": "EVALUACION_AS",
    "contexto_tipo": "SOCIO_COMUNITARIO",
    "secciones": [
        seccion("Identificación", [
            pregunta("Nombre del Socio Comunitario (Institución, Empresa o Comunidad)", c.TEXTO_CORTO),
            pregunta(
                '¿Con estudiantes de qué carrera trabajó? Si no se acuerda o no sabe indíquelo en la última '
                'opción "Otras".',
                c.LISTA,
                [
                    'Administración Pública',
                    'Arquitectura',
                    'Ingeniería en Control de Gestión',
                    'Derecho',
                    'Enfermería',
                    'Fonoaudiología',
                    'Ingeniería Civil Industrial',
                    'Ingeniería Civil Informática',
                    'Ingeniería Civil Química',
                    'Ingeniería Comercial',
                    'Ingeniería en Administración',
                    'Ingeniería en Construcción',
                    'Kinesiología',
                    'Licenciatura en Artes Visuales',
                    'Medicina',
                    'Nutrición y Dietética',
                    'Obstetricia y Puericultura',
                    'Odontología',
                    'Pedagogía en Educación Básica',
                    'Pedagogía en Educación Diferencial',
                    'Pedagogía en Educación Física',
                    'Pedagogía en Educación Parvularia',
                    'Pedagogía en Historia Geografía y Cs. Sociales',
                    'Pedagogía en Inglés',
                    'Pedagogía en Lengua Castellana y Comunicación',
                    'Periodismo',
                    'Psicología',
                    'Publicidad y Comunicación Integral',
                    'Química y Farmacia',
                    'Terapia Ocupacional',
                    'Trabajo Social',
                    'Otras',
                ],
            ),
            pregunta("Nombre completo de quien esta respondiendo esta encuesta", c.TEXTO_CORTO, dato_respondente="nombre"),
            pregunta("Como se identifica", c.ALTERNATIVA_UNICA, [
                'Socio Comunitario (Institución que agrupa a beneficiarios)',
                'Beneficiario',
            ]),
            pregunta("Indicar sede de los estudiantes con los cuales trabajó", c.ALTERNATIVA_UNICA, [
                'Santiago',
                'Talca',
                'Temuco',
            ]),
        ]),
    ],
}

DOCENTES = {
    "codigo": "EVALUACION_AS_DOCENTES",
    "titulo": "ENCUESTA EVALUACIÓN A+S DOCENTES 2026",
    "descripcion": (
        "Estimado/a docente, junto con agradecer su participación, entusiasmo y motivación durante este "
        "semestre/trimestre para implementar actividades de A+S, le invitamos a responder la siguiente encuesta. "
        "Es importante que responda con sinceridad y comente lo que sea necesario, sus respuestas ayudarán a "
        "mejorar futuras versiones de la implementación de A+S. La información que entregue será usada para "
        "análisis de la asignatura y para análisis institucional, los resultados serán reportados resguardando "
        "siempre el anonimato de las respuestas."
    ),
    "proceso": "EVALUACION_AS",
    "contexto_tipo": "DOCENTE",
    "secciones": [
        seccion("Identificación", [
            pregunta("Rut", c.RUT, dato_respondente="rut"),
            pregunta("Semestre", c.ALTERNATIVA_UNICA, [
                'Otoño',
                'Primavera',
            ]),
            pregunta("Carrera", c.LISTA, [
                'Administración Pública',
                'Auditoría e Ingeniería en Control de Gestión',
                'Derecho',
                'Enfermería',
                'Fonoaudiología',
                'Ingeniería Civil Industrial',
                'Ingeniería Civil Informática',
                'Ingeniería Civil Química',
                'Ingeniería Comercial',
                'Ingeniería en Construcción',
                'Kinesiología',
                'Medicina',
                'Nutrición y Dietética',
                'Obstetricia y Puericultura',
                'Odontología',
                'Pedagogía en Educación Básica con mención en Educación Matemática',
                'Pedagogía en Educación Básica con mención en Lenguaje y Comunicación',
                'Pedagogía en Educación Física',
                'Pedagogía en Educación Parvularia',
                'Pedagogía en Inglés',
                'Psicología',
                'Publicidad y Comunicación Integral',
                'Química y Farmacia',
                'Terapia Ocupacional',
                'Trabajo Social',
                'Técnico Universitario en Administración',
                'Arquitectura',
                'Formación General Corporativa',
                'Relaciones Públicas',
                'Pedagogía en Lengua Castellana y Comunicación',
                'Pedagogía en Historia y Geografía',
                'Licenciatura en Artes Visuales',
                'Ingeniería en Informática',
                'Pedagogía en Educación Diferencial',
                'Otras',
            ]),
            pregunta("Asignatura (describa el nombre formal y completo de la asignatura)", c.TEXTO_CORTO),
            pregunta("Selecciona el Campus o Sede donde realizaste la asignatura", c.ALTERNATIVA_UNICA, [
                'Sede Santiago Campus El Llano',
                'Sede Santiago Campus Providencia',
                'Sede Talca',
                'Sede Temuco',
            ]),
        ]),
    ],
}
