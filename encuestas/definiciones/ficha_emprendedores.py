"""
Ficha de Inscripción de Emprendedores A+S: junta en un formulario con pestañas
por programa las tres fichas que hoy se envían por separado (Investigación de
Mercados, Consultoría Empresas y Gestión de Procesos de Negocios). Las
preguntas comunes se responden una vez y las de cada programa aparecen solo
con su pestaña.
"""

from encuestas import constantes as c
from encuestas.semillas import opcion, otras, pregunta, seccion

INV_MERCADOS = "INV_MERCADOS"
CONSULTORIA = "CONSULTORIA_EMPRESAS"
GESTION_PROCESOS = "GESTION_PROCESOS"
SIN_CONSULTORIA = [INV_MERCADOS, GESTION_PROCESOS]


def solo(programas):
    return ("programa", programas)


INTRO_INV_MERCADOS = 'La Universidad Autónoma de Chile, a través de la asignatura Investigación de Mercados de la carrera de Ingeniería Comercial, invita a emprendedores y pequeñas empresas a participar en un proceso de investigación de mercado aplicada, orientada a responder preguntas concretas sobre su producto, servicio o negocio. Este estudio consiste en una investigación cuantitativa de una medición, desarrollada principalmente mediante encuestas, que permitirá obtener información relevante para comprender mejor a sus clientes y apoyar la toma de decisiones de su emprendimiento. El trabajo será realizado por estudiantes de la carrera, bajo la supervisión directa de un profesor, quien velará por el correcto desarrollo de todas las etapas del proceso investigativo. Entre los temas que se pueden abordar se encuentran, por ejemplo:\nConocimiento y posicionamiento de marca\nMotivaciones de compra de los clientes\nEvaluación de calidad de servicio\nComparación con competidores\nPercepción de productos o servicios\nPre testeo de piezas publicitarias\nOtras preguntas relevantes para su negocio\nPara que la investigación sea exitosa, será importante contar con su colaboración y con información básica de su emprendimiento, lo que permitirá evaluar la factibilidad del estudio. Esta iniciativa se desarrolla bajo la metodología Aprendizaje + Servicio (A+S), mediante la cual los estudiantes aplican sus conocimientos en situaciones reales, generando a la vez un aporte concreto a emprendedores de la comunidad. 🕒 Este formulario le tomará aproximadamente 4 minutos en completarse. 🔒 Toda la información entregada será tratada con estricta confidencialidad y utilizada únicamente con fines académicos. Su participación es muy importante, ya que contribuye tanto a la formación de nuestros estudiantes como al fortalecimiento de los emprendimientos participantes.'
INTRO_CONSULTORIA = 'La Universidad Autónoma, a través de la cátedra Consultoría Empresas de la carrera de Ingeniería Civil Industrial pone a disposición de quienes lo pudieran requerir la oferta de una asesoría integral con alumnos de 4to año de la carrera dirigidos por 2 docentes de la universidad,\n\nProductos a entregar:\n\nLas beneficiarias contarán con un informe en el ámbito de desarrollo de la consultoría, donde se detalla el trabajo de análisis y las propuestas de acuerdo a las necesidades de cada negocio:\n\nLos temas a tratar se indican más abajo\n\nPerfil de Empresas:\nMicro y pequeña empresa.\n\nCaracterística de las organizaciones:\nFormalizadas, con un tiempo de facturación de al menos 2 años.\n\nTiempo requerido para reuniones de trabajo (alumnos y beneficiaria):\nAl menos 3 sesiones de 90 minutos como mínimo entre agosto y noviembre 2025  (presentación, recopilación de antecedentes, borrador de avance) pueden ser presencial u online. La oportunidad y número de sesiones se pactan directamente con los estudiantes de comun acuerdo.\n\nEntrega del Informe Final\nEn forma presencial durante el mes de Noviembre 2025\n\nUsted puede elegir los temas que más le interesen,  los profesores decidirán cual de ellos  es el que más se acerca a sus necesidades actuales para llevarlo a cabo.\n\nLa información por usted entregada durante el proceso será de carácter estrictamente confidencial.\nTrabajamos utilizando una metodología llamada Aprendizaje + Servicio (A+S) donde los estudiantes de la Universidad Autónoma aplican sus conocimiento en base a casos reales entregando un servicio de calidad, por lo que su participación en este programa es muy importante para nosotros.\n\nLos emprendedores seleccionados se citarán a una reunión OnLines durante el mes de agosto para resolver dudas e indicar detalles de la intervención\nSe invitará a los emprendedores seleccionados a una presentación al final del semestre (fines de noviembre) a la universidad, donde podrán compartir con los docentes y profesores de la carrera.'
INTRO_GESTION_PROCESOS = 'Las organizaciones, en su proceso de crecimiento y mejora continua, buscan optimizar la forma en que desarrollan sus actividades. Muchas veces, ordenar y revisar los procesos de trabajo permite ahorrar tiempo, reducir errores y mejorar el servicio a los clientes. En este contexto, la Escuela de Ingeniería de Control y Gestión de la Universidad Autónoma de Chile invita a empresas, emprendedores y organizaciones a participar en una Clínica Empresarial de Gestión de Procesos, donde estudiantes trabajarán en el análisis y mejora de procesos operativos y de negocio. Durante esta experiencia, un equipo de estudiantes —guiados por un profesor— desarrollará un diagnóstico y propuestas de mejora orientadas a optimizar el funcionamiento de su organización. El trabajo podrá considerar, entre otros aspectos:\nLevantamiento de procesos y detección de brechas, para comprender cómo se desarrollan actualmente las actividades del negocio.\nAnálisis y propuestas de mejora de procesos, orientadas a hacer el trabajo más eficiente.\nIdentificación de puntos críticos del proceso, donde sea necesario revisar errores, tiempos o costos.\nPropuestas prácticas para simplificar y mejorar los procesos, buscando que sean más claros, rápidos y ordenados.\nDiseño de indicadores simples, que permitan monitorear el desempeño y apoyar la toma de decisiones.\nBeneficios de participar Las organizaciones participantes podrán obtener:\nIdentificación de pérdidas de tiempo o reprocesos en sus procesos actuales.\nDetección de posibles errores operativos y oportunidades de mejora.\nPropuestas para mejorar tiempos de atención o eficiencia operativa.\nIndicadores simples para evaluar si los procesos están mejorando.\nUn informe claro y aplicable con recomendaciones de mejora.\nEsta iniciativa se desarrolla bajo la metodología Aprendizaje + Servicio (A+S), mediante la cual los estudiantes de la Universidad Autónoma aplican sus conocimientos en situaciones reales, generando a la vez un aporte concreto a empresas y organizaciones de la comunidad. 🕒 Este formulario le tomará aproximadamente 4 minutos en completarse. 🔒 Toda la información entregada será tratada con estricta confidencialidad y utilizada únicamente con fines académicos. Su participación es muy valiosa, ya que contribuye tanto a la formación de nuestros estudiantes como al fortalecimiento de las organizaciones participantes.'

DEFINICION = {
    "codigo": "FICHA_EMPRENDEDORES",
    "titulo": "Ficha de Inscripción de Emprendedores A+S",
    "descripcion": (
        "Seleccione el programa al que desea inscribirse. "
        "Se mostrarán la información y las preguntas de ese programa."
    ),
    "proceso": "INSCRIPCION_EMPRENDEDORES",
    "contexto_tipo": "EMPRENDEDOR",
    "secciones": [
        seccion("Programa", [
            pregunta("Seleccione el programa al que desea inscribirse", c.SELECTOR_PROGRAMA, [
                opcion('Investigación de Mercados (Ingeniería Comercial)', valor=INV_MERCADOS, carrera='Comercial'),
                opcion('Consultoría Empresas (Ingeniería Civil Industrial)', valor=CONSULTORIA, carrera='Civil Industrial'),
                opcion('Gestión de Procesos de Negocios (Ingeniería de Control y Gestión)', valor=GESTION_PROCESOS, carrera='Control'),
            ], clave="programa"),
        ]),
        seccion('Ficha de Inscripción Emprendedores Investigación de Mercados', [], descripcion=INTRO_INV_MERCADOS, si=solo([INV_MERCADOS])),
        seccion('Ficha Inscripción Emprendedores Programa Consultoría Empresas 2026 Ing. Civil Industrial', [], descripcion=INTRO_CONSULTORIA, si=solo([CONSULTORIA])),
        seccion('Ficha de Inscripción en Programa de Gestión de Procesos de Negocios 2026', [], descripcion=INTRO_GESTION_PROCESOS, si=solo([GESTION_PROCESOS])),
        seccion('Datos de contacto', [
            pregunta('Nombre Completo', c.TEXTO_CORTO, dato_respondente='nombre'),
            pregunta('RUT', c.RUT, dato_respondente='rut'),
            pregunta('Correo electrónico de contacto', c.CORREO, dato_respondente='correo'),
            pregunta('Telefono de Contacto +569...', c.TEXTO_CORTO, ayuda='Ejemplo: +56 9 1234 5678'),
            pregunta('Nombre de su emprendimiento', c.TEXTO_CORTO),
            pregunta('Producto o servicio que comercializa', c.TEXTO_CORTO),
        ]),
        seccion('Formalización', [
            pregunta('Está Formalizado?', c.ALTERNATIVA_UNICA, [
                'Si',
                'No',
                'En Proceso de Formalización',
            ]),
        ], si=solo(SIN_CONSULTORIA)),
        seccion('Su emprendimiento', [
            pregunta('Rubro (Alimentación, Comercio, Servicios, etc.)', c.TEXTO_CORTO),
            pregunta('Antiguedada de su emprendimiento', c.ALTERNATIVA_UNICA, [
                opcion('Menos de 1 año', solo_si=solo(SIN_CONSULTORIA)),
                'Entre 1 y 2 años',
                'Más de 2 años',
            ]),
            pregunta('Indiquenos cuantas personas trabajan con usted', c.ALTERNATIVA_UNICA, [
                opcion('Solo yo', solo_si=solo(SIN_CONSULTORIA)),
                '2 persona',
                '3 personas',
                'Más de 3 personas',
                opcion('Otras', otras=True, solo_si=solo([CONSULTORIA])),
            ]),
            pregunta('Favor indiquemos a que Centro de Negocios de Sercotec esta asociado, si es que lo esta.', c.TEXTO_CORTO, obligatoria=False),
            pregunta('Favor indíquenos el nombre del  ASESOR del Centro de Negocios Sercotec con que está trabajando.', c.TEXTO_CORTO, obligatoria=False),
            pregunta('Favor indiquenos el correo electrónico de su asesor Sercotec para invitarlo a una primera reunión junto con usted', c.CORREO, obligatoria=False),
        ]),
        seccion('Temas de apoyo', [
            pregunta('En que otros temas podríamos brindarle apoyo con los alumnos y profesores de la Facultad de Administración y Negocios de la Universidad Autónoma', c.TEXTO_LARGO, obligatoria=False),
        ], si=solo([INV_MERCADOS])),
        seccion('Temas de apoyo', [
            pregunta('En qué temas  de los indicados  podríamos brindarle apoyo con los alumnos y profesores de la Facultad de Ingeniería de la Universidad Autónoma (Se permite indicar más de uno)', c.SELECCION_MULTIPLE, [
                'Consultoría en Gestión de Inventarios',
                'Consultoría Financiera, Costos, flujos, indicadores, etc.',
                'Consultoría de Recursos Humanos y Desarrollo Organizacional: (Reclutamiento y selección de personal, Desarrollo organizacional, Evaluación del desempeño, Capacitación, etc)',
                'Consultoría en Propuestas de productos/servicios, mejoras, nuevos productos, etc.',
                'Consultoría de Operaciones (optimización de Procesos, Gestión de la cadena de suministros, Control de calidad, Mejora continua)',
                'Realizar un Estudio de Mercado en la localidad donde se encuentre el emprendedor',
                otras(),
            ]),
            pregunta('Le agradeceremos indicarnos dirección de su página web y/o redes sociales si  las tiene (Instagram, X u otra)', c.TEXTO_CORTO, obligatoria=False),
            pregunta('En este espacio, nos puede indicar algún comentario y/o requerimiento especial que necesite. Horarios para comunicarse con Ud. Otros temas de su interés, etc.', c.TEXTO_LARGO, obligatoria=False),
        ], si=solo([CONSULTORIA])),
        seccion('Temas de apoyo', [
            pregunta('En qué otros temas podríamos brindarle apoyo con los alumnos y profesores de la Universidad', c.SELECCION_MULTIPLE, [
                'Investigación de Mercados asociada a su emprendimiento en partícular',
                'Asesoría integral (Finanzas, Marketing, Recursos Humanos, etc)',
                'Confeccionar su página Web o Sitio Web',
                'Innovación asociada a su emprendimiento',
                'Asesoría en Sostenibilidad',
                'Resolución de problemas técnicos, con ingenieros',
                'Asesoría en etiquetado de productos alimenticios',
                otras(),
            ]),
        ], si=solo([GESTION_PROCESOS])),
    ],
}
