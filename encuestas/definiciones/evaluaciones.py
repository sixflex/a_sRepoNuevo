"""
Encuestas de Evaluación A+S 2026 para estudiantes, Socios Comunitarios y
docentes (forms del cliente).

Las preguntas de valoración de 1 a 5 son cuadrículas como en Microsoft Forms
(una fila por afirmación). Su dimensión y la valoración general alimentan los
anillos de satisfacción del panel del coordinador (core/indicadores.py).
"""

from encuestas import constantes as c
from encuestas.semillas import cuadricula, otras, pregunta, seccion

# Alternativas de horas de dedicación (estudiantes y docentes).
HORAS = ["1-2 horas.", "3-4 horas.", "5-6 horas.", "7 ó más horas."]

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
        seccion('Dimensión: Aprendizaje', [
            *cuadricula(7, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy De Acuerdo".', [
                'El docente explicó que se trabajaría con A+S y el sentido de aprender con esta metodología.',
                'Apliqué los aprendizajes de la asignatura, en la realización del servicio.',
                'El servicio estaba claramente relacionado con lo que tenía que aprender en el curso (resultados de aprendizaje o criterios de evaluación del programa).',
                'A partir del servicio realizado, pude identificar aprendizajes que me faltan por adquirir o en los cuales debo avanzar.',
                'A partir del servicio realizado, identifiqué lo que soy capaz de aportar, como profesional en formación.',
            ], dimension="aprendizaje"),
        ]),
        seccion('Dimensión: Seguimiento de los resultados de aprendizaje (balance de carga académica)', [
            pregunta('¿Cuántas horas a la semana dedicaste a las actividades realizadas en clase (presenciales)?', c.ALTERNATIVA_UNICA, HORAS),
            pregunta('¿Cuántas horas semanales dedicaste a las actividades encomendadas para tus horas de trabajo autónomo (fuera del horario de clases)?', c.ALTERNATIVA_UNICA, HORAS),
            pregunta('¿Qué actividades me fueron indicadas para realizar en horario fuera de clases?', c.SELECCION_MULTIPLE, [
                'Lectura previa.',
                'Preparación de informes.',
                'Desarrollo de guías de trabajo.',
                'Preparación de presentaciones orales.',
                'Trabajo en terreno.',
                'Realización de proyectos.',
                'Estudio personal para evaluación.',
                'Otro',
            ]),
        ]),
        seccion('Dimensión: Competencias integrales', [
            pregunta('¿Qué indicador de habilidades de Comunicación lograste desarrollar en mayor profundidad durante tu experiencia con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Sinteticé las ideas y argumentos que se desprenden de una lectura crítica de distintos tipos de textos.',
                'Comuniqué efectivamente situaciones problemáticas, que permitieron buscar soluciones pertinentes.',
                'Planteé soluciones viables de manera oral y escrita, frente a situaciones problemáticas relativas a contexto.',
                'Identifiqué y comuniqué los desafíos presentes, propuse respuestas concretas y contextualizadas, adaptadas a las necesidades reales del entorno.',
                'Redacté informes disciplinares con una secuencia lógica, utilizando lenguaje técnico y respetando normas ortográficas.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Trabajo en Equipo desarrollaste en mayor profundidad al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Argumenté mis ideas para aportar a una solución frente a una situación o problema.',
                'Valoré las ideas que aportan otras personas para dar una solución frente a una situación o problema.',
                'Demostré liderazgo en el equipo de trabajo, motivándolo a participar activamente, para el logro de los objetivos planteados.',
                'Respeté los roles y las funciones de las personas que integraron mi equipo de trabajo.',
                'Autoevalué los resultados de mi propio quehacer frente a determinadas acciones, buscando estrategias para superarme.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Pensamiento Crítico desarrollaste en mayor profundidad al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Demostré postura personal y argumenté frente a una situación determinada, a partir del análisis de distintas fuentes de información.',
                'Propuse alternativas de solución, a partir de análisis crítico de la información o situación.',
                'Fundamenté mis conclusiones sobre la base de la evidencia y del análisis crítico de distintas fuentes de información.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Comportamiento Ético desarrollaste en profundidad al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Respeté las normas de conducta que regulan el contexto en el que me desenvuelvo.',
                'Evalúe el impacto que tendrá mi proceder en otras personas y su entorno.',
                'Apliqué las normas éticas vigentes para el uso de la información.',
                'Actúe respetando las normativas legales vigentes en las funciones que me corresponde desempeñar.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Responsabilidad Social desarrollaste al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Elaboré estudios sobre las condiciones de mi entorno social, económico y político, utilizando distintas técnicas de recogida de información.',
                'Promoví acciones que fomentan el cuidado y respeto personal hacia los otros, la comunidad y el entorno.',
                'Diseñé planes de acción centrado en objetivos sociales específicos.',
            ]),
        ]),
        seccion('Dimensión: Reflexión', [
            *cuadricula(16, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy De Acuerdo".', [
                'Se realizaron actividades de reflexión relacionadas al servicio.',
                'Las instancias de reflexión me permitieron relacionar la experiencia de servicio con los aprendizajes de la asignatura.',
                'Las instancias de reflexión, me permitieron relacionar el servicio con la competencia genérica de mi asignatura.',
                'Reflexioné antes, durante y después del servicio, sobre los efectos de mis propuestas en los beneficiarios y su entorno.',
            ], dimension="reflexion"),
        ]),
        seccion('Dimensión: Servicio', [
            *cuadricula(17, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy De Acuerdo".', [
                'El servicio realizado buscó satisfacer/responder a una necesidad de la comunidad o socio comunitario.',
                'Profundicé en la realidad y características del socio comunitario con quien me vinculé durante el semestre.',
                'Realicé un servicio que fue un aporte al socio comunitario o a la comunidad con la que trabajé.',
            ], dimension="servicio"),
        ]),
        seccion('Dimensión: Socio comunitario', [
            *cuadricula(18, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy De Acuerdo".', [
                'El socio comunitario, colaboró con lo que realizamos (por ejemplo, entregó información, contestó consultas, participó de reuniones, entre otras).',
            ], dimension="socio_comunitario"),
        ]),
        seccion('Dimensión: Valoración de la metodología A+S', [
            *cuadricula(19, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy Negativo" y 5 es "Muy Positivo".', [
                '¿Qué tan positivo fue aprender con A+S?',
                '¿El proyecto A+S contribuye a tu futuro ejercicio profesional?',
                'Fue motivante para mí, aprender con esta metodología.',
                '¿Consideras que tu participación en esta actividad contribuye al logro de las competencias planteadas en el perfil de egreso de tu carrera?',
                '¿Consideras que la realización de esta actividad potencia tus competencias para ingresar al mundo laboral?',
                '¿Consideras que participar de esta iniciativa te permite poner en práctica valores como el comportamiento ético, respeto, equidad y la responsabilidad social?',
            ], minimo="Muy Negativo", maximo="Muy Positivo", valoracion_general=True, perfil_egreso="D"),
            pregunta('Señala aquellos aspectos positivos de la experiencia con A+S.', c.TEXTO_LARGO, obligatoria=False),
            pregunta('Señala aquellos aspectos que piensa deben mejorar en la experiencia A+S.', c.TEXTO_LARGO, obligatoria=False),
        ]),
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
        seccion('Categoría: Competencias genéricas', [
            pregunta('¿Cuál de los siguientes indicadores de Habilidades de Comunicación destacaría de los y las estudiantes?', c.ALTERNATIVA_UNICA, [
                'Sintetizan las ideas y argumentos que desprenden de una lectura crítica de distintos tipos de textos.',
                'Comunican efectivamente situaciones problemáticas, que permitan buscar soluciones pertinentes.',
                'Plantean soluciones viables de manera oral y escrita, frente a situaciones problemáticas relativas a su contexto.',
                'Identifican y comunican los desafíos presentes, proponen respuestas concretas y contextualizadas, adaptadas a las necesidades reales de su entorno.',
                'Redactan informes disciplinares con una secuencia lógica, utilizando lenguaje técnico y respetando normas ortográficas.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Trabajo en Equipo destaca de la ejecución observada en los/as estudiantes?', c.ALTERNATIVA_UNICA, [
                'Argumentan sus ideas para aportar a una solución frente a una situación o problema.',
                'Valoran las ideas que aportan otras personas para dar una solución frente a una situación o problema.',
                'Demuestran liderazgo en el equipo de trabajo, motivándolo a participar activamente, para el logro de los objetivos planteados.',
                'Respetan los roles y las funciones de las personas que integran su equipo de trabajo.',
                'Autoevalúan los resultados de su propio quehacer frente a determinadas acciones, buscando estrategias para superarse.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Pensamiento Crítico observa más desarrollado en los/as estudiantes?', c.ALTERNATIVA_UNICA, [
                'Demuestran postura personal y argumentan frente a una situación determinada, a partir del análisis de distintas fuentes de información.',
                'Propone alternativas de solución, a partir de análisis crítico de la información o situación.',
                'Fundamentan sus conclusiones sobre la base de la evidencia y del análisis crítico de distintas fuentes de información.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Comportamiento Ético observa más desarrollado en los/as estudiantes?', c.ALTERNATIVA_UNICA, [
                'Respetan las normas de conducta que regulan el contexto en el que se desenvuelven.',
                'Evalúan el impacto que tendrá su proceder en otras personas y su entorno.',
                'Aplican las normas éticas vigentes para el uso de la información.',
                'Actúan respetando las normativas legales vigentes en las funciones que les corresponde desempeñar.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Responsabilidad Social observa más desarrollados en los/as estudiantes?', c.ALTERNATIVA_UNICA, [
                'Elaboran estudios sobre las condiciones de su entorno social, económico y político, utilizando distintas técnicas de recogida de información.',
                'Promueven acciones que fomentan el cuidado y respeto personal hacia los otros, la comunidad y el entorno.',
                'Diseñan planes de acción centrados en objetivos sociales específicos.',
            ]),
        ]),
        seccion('Categoría: Servicio', [
            *cuadricula(11, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy de Acuerdo".', [
                'El servicio realizado fue un aporte para mí y/o para la comunidad a la que represento.',
                'El servicio respondió a un problema/necesidad del socio comunitario.',
                'Se profundizó en la realidad del socio comunitario.',
                '¿Considera que la atención recibida contribuye al mejoramiento de su bienestar, salud o calidad de vida?',
            ], dimension="servicio"),
        ]),
        seccion('Categoría: Valoración de la Universidad Autónoma', [
            *cuadricula(12, 'Entrega tu valoración general puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy de Acuerdo".', [
                'Mantuve permanente contacto con los estudiantes durante la realización del servicio.',
                'Mantuve permanente contacto con el profesor de los estudiantes con los que trabajé.',
                'La Universidad Autónoma se comunicó conmigo en forma clara y fluida.',
                'Establecimos un acuerdo formal de colaboración con la Universidad Autónoma.',
                'Fue positivo trabajar con estudiantes de la Universidad Autónoma.',
                '¿Volvería a participar en una actividad académica/ A+S de la Universidad Autónoma de Chile?',
            ], dimension="universidad", valoracion_general=True),
            pregunta('Señale aquellos aspectos positivos de la experiencia con A+S.', c.TEXTO_LARGO, obligatoria=False),
            pregunta('Señale aquellos aspectos que piensa deben mejorar en la experiencia A+S.', c.TEXTO_LARGO, obligatoria=False),
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
        seccion('Dimensión: Aprendizaje', [
            *cuadricula(6, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy de Acuerdo".', [
                'Se explicó a los estudiantes la Metodología A+S y los beneficios que trae consigo.',
                'Incorporé los resultados de aprendizaje de la asignatura en la realización del servicio.',
                'Se evidenció el aporte de la Metodología A+S al desempeño de los/las estudiantes para el futuro profesional.',
            ], dimension="aprendizaje"),
        ]),
        seccion('Dimensión: Seguimiento de los resultados de aprendizaje (balance de carga académica)', [
            pregunta('¿Cuántas horas a la semana, dedicó a las actividades realizadas en clase?', c.ALTERNATIVA_UNICA, HORAS),
            pregunta('¿Cuántas horas semanales piensa que le dedicaron los estudiantes a las actividades encomendadas en su horario autónomo (fuera del horario de clases)?', c.ALTERNATIVA_UNICA, HORAS),
            pregunta('¿Qué actividades le indicó a los estudiantes que debían realizar en horario autónomo?', c.SELECCION_MULTIPLE, [
                'Lectura previa.',
                'Preparación de informes.',
                'Desarrollo de guías de trabajo.',
                'Preparación de presentaciones orales.',
                'Trabajo en terreno.',
                'Realización de proyectos.',
                'Estudio personal para evaluación y otros.',
                otras(),
            ]),
        ]),
        seccion('Dimensión: Competencias integrales', [
            pregunta('¿Cuál de los siguientes indicadores de Habilidades de Comunicación desarrolló en mayor profundidad en los estudiantes al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Sintetiza las ideas y argumentos que desprende de una lectura crítica de distintos tipos de textos.',
                'Comunica efectivamente situaciones problemáticas, que permitan buscar soluciones pertinentes.',
                'Plantea soluciones viables de manera oral y escrita, frente a situaciones problemáticas relativas a su contexto.',
                'Identifica y comunica los desafíos presentes, propone respuestas concretas y contextualizadas, adaptadas a las necesidades reales del entorno.',
                'Redacta informes disciplinares con una secuencia lógica, utilizando lenguaje técnico y respetando normas ortográficas.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Trabajo en Equipo promovió en mayor profundidad en los estudiantes al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Argumenta sus ideas para aportar a una solución frente a una situación o problema.',
                'Valora las ideas que aportan otras personas para dar una solución frente a una situación o problema.',
                'Demuestra liderazgo en el equipo de trabajo, motivándolo a participar activamente, para el logro de los objetivos planteados.',
                'Respeta los roles y las funciones de las personas que integran su equipo de trabajo.',
                'Autoevalúa los resultados de su propio quehacer frente a determinadas acciones, buscando estrategias para superarse.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Pensamiento Crítico promovió en mayor profundidad en los estudiantes al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Demuestra postura personal y argumenta frente a una situación determinada, a partir del análisis de distintas fuentes de información.',
                'Propone alternativas de solución, a partir de análisis crítico de la información o situación.',
                'Fundamenta sus conclusiones sobre la base de la evidencia y del análisis crítico de distintas fuentes de información.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Comportamiento Ético logró promover en mayor profundidad en los estudiantes al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Respeta las normas de conducta que regulan el contexto en el que se desenvuelve.',
                'Evalúa el impacto que tendrá su proceder en otras personas y su entorno.',
                'Aplica las normas éticas vigentes para el uso de la información.',
                'Actúa respetando las normativas legales vigentes en las funciones que le corresponde desempeñar.',
            ]),
            pregunta('¿Cuál de los siguientes indicadores de Responsabilidad Social logró desarrollar en profundidad en los estudiantes al trabajar con la metodología A+S?', c.ALTERNATIVA_UNICA, [
                'Elabora estudios sobre las condiciones de su entorno social, económico y político, utilizando distintas técnicas de recogida de información.',
                'Promueve acciones que fomentan el cuidado y respeto personal hacia los otros, la comunidad y el entorno.',
                'Diseña planes de acción centrados en objetivos sociales específicos.',
            ]),
        ]),
        seccion('Dimensión: Reflexión', [
            *cuadricula(15, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy De Acuerdo".', [
                'Se realizaron actividades de reflexión relacionadas al servicio.',
                'Las instancias de reflexión, me permitieron intencionar el logro de los resultados de aprendizaje y las competencias genéricas.',
                'Propicié la reflexión antes, durante y después del servicio, en relación a los efectos que sus propuestas tuvieron en los beneficiarios y su entorno.',
            ], dimension="reflexion"),
        ]),
        seccion('Dimensión: Servicio', [
            *cuadricula(16, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy en Desacuerdo" y 5 es "Muy De Acuerdo".', [
                'El servicio realizado buscó satisfacer/responder a una necesidad de la comunidad o socio comunitario.',
                'Los estudiantes fueron capaces de profundizar en la realidad y características del socio comunitario, durante el semestre.',
                'Los estudiantes lograron realizar un servicio que fue un aporte al socio o a la comunidad.',
            ], dimension="servicio"),
        ]),
        seccion('Dimensión: Socio comunitario', [
            *cuadricula(17, 'Entrega tu valoración general, puntuando de 1 a 5 cada pregunta, donde 1 es "Muy Negativo" y 5 es "Muy Positivo".', [
                'El Socio Comunitario cumplió con los acuerdos establecidos al inicio del proyecto.',
            ], dimension="socio_comunitario", minimo="Muy Negativo", maximo="Muy Positivo"),
        ]),
        seccion('Dimensión: Valoración general', [
            *cuadricula(18, 'Entrega tu valoración general puntuando de 1 a 5 cada pregunta, donde 1 es "Muy Negativo" y 5 es "Muy Positivo".', [
                'Qué tan positivo fue trabajar con la Metodología A+S.',
                'Aplicar la Metodología A+S en mis procesos de enseñanza, fue positivo para fortalecer los ejes de Responsabilidad Social Universitaria y centralidad en el estudiante.',
                'Fue motivante para mí utilizar y conocer sobre esta metodología.',
                '¿Considera usted que la realización de esta actividad por parte de sus estudiantes contribuye al desarrollo de las competencias del perfil de egreso?',
                '¿Considera que la actividad potencia las competencias para la futura empleabilidad de sus estudiantes?',
                '¿Considera que la realización de esta actividad incorpora elementos que aportan al desarrollo de la cultura de responsabilidad social universitaria en sus estudiantes?',
            ], minimo="Muy Negativo", maximo="Muy Positivo", valoracion_general=True, perfil_egreso="D"),
            pregunta('Señale aquellos aspectos positivos de la experiencia con A+S.', c.TEXTO_LARGO, obligatoria=False),
            pregunta('Señale aquellos aspectos que piensa deben mejorar en la experiencia A+S.', c.TEXTO_LARGO, obligatoria=False),
        ]),
    ],
}
