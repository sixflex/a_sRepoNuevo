
from encuestas import constantes as c
from encuestas.semillas import otras, pregunta, seccion

DEFINICION = {
    "codigo": "REGISTRO_SOCIO_COMUNITARIO_AS_2026",
    "titulo": "Registro de Socio Comunitario A+S 2026",
    "proceso": "GENERAL",
    "contexto_tipo": "SOCIO_COMUNITARIO",
    "secciones": [
        seccion("Datos de quien responde", [
            pregunta("Nombre completo de quien esta respondiendo esta encuesta", c.TEXTO_CORTO, dato_respondente="nombre"),
            pregunta("Rut (sin puntos y con guion", c.RUT, dato_respondente="rut"),
            pregunta("Correo electrónico", c.CORREO, dato_respondente="correo"),
            pregunta("Como se identifica", c.ALTERNATIVA_UNICA, [
                "Docente asignatura A+S vinculada a carrera",
                "Docente de Asignatura FG",
                "Estudiante"
            ]),
        ]),
        seccion("Datos académicos", [
            pregunta("Sede", c.ALTERNATIVA_UNICA, [
                "Santiago", "Talca", "Temuco"
            ]),
            pregunta("Facultad", c.LISTA, [
                "Administración y Negocios",
                "Arquitectura, Construcción y Medio Ambiente",
                "Ciencias de la Salud",
                "Ciencias Sociales y Humanidades",
                "Derecho",
                "Educación",
                "Ingeniería",
                "Formación General"
            ]),
            pregunta("Carrera", c.LISTA, [
                "Formación General",
                "Ingeniería en Control de Gestión",
                "Ingeniería en Administración",
                "Ingeniería Comercial",
                "Ingeniería en Construcción",
                "Arquitectura",
                "Enfermería",
                "Fonoaudiología",
                "Kinesiología",
                "Nutrición y Dietética",
                "Medicina",
                "Obstetricia y Puericultura",
                "Odontología",
                "Química y Farmacia",
                "Terapia Ocupacional",
                "Administración Pública",
                "Periodismo",
                "Psicología",
                "Publicidad y Comunicación Integral",
                "Trabajo Social",
                "Derecho",
                "Pedagogía en Educación Básica",
                "Pedagogía en Educación Física",
                "Pedagogía en Educación Parvularia",
                "Pedagogía en Inglés",
                "Pedagogía en Educación Diferencial",
                "Licenciatura en Artes Visuales",
                "Pedagogía en Historia, Geografía y Cs. Sociales",
                "Pedagogía en Lengua Castellana y Comunicación",
                "Ingeniería Civil Industrial",
                "Ingeniería Civil Química",
                "Ingeniería Civil Informática",
                "Otras"
            ]),
            pregunta("Nombre Asignatura", c.TEXTO_CORTO),
        ]),
        seccion("Datos del socio comunitario", [
            pregunta("Nombre del Socio Comunitario (Institución, Empresa o Comunidad)", c.TEXTO_CORTO),
            pregunta("Representante Socio Comunitario", c.TEXTO_CORTO),
            pregunta("Cargo del Representante Socio Comunitario", c.TEXTO_CORTO),
            pregunta("Teléfono de contacto con el Socio Comunitario", c.TEXTO_CORTO),
            pregunta("Correo electrónico del Socio Comunitarios", c.CORREO),
            pregunta("Comuna a la que pertenece el Socio Comunitario", c.TEXTO_CORTO),
            pregunta("Dirección", c.TEXTO_CORTO),
            pregunta("Clasifique al Socio Comunitarios", c.ALTERNATIVA_UNICA, [
                "Municipalidad",
                "Corporación",
                "Fundación",
                "Cesfam",
                "Colegio",
                "CDN Sercotec",
                "Junta de Vecinos",
                "Club de Adulto Mayor",
                "Club deportivo",
                "Emprendedor(a) - Pyme",
                "Universidad Autónoma",
                otras("Otras")
            ]),
        ]),
        seccion("Experiencia y evaluación", [
            pregunta("Año en el que trabajo con el SC", c.SELECCION_MULTIPLE, [
                "2021", "2022", "2023", "2024", "2025", "2026"
            ]),
            pregunta("Número de BENEFICIARIOS (personas) que se llegó a favorecer con el proyecto A+S (aproximadamente)", c.NUMERO),
            pregunta("Explique en no más de tres líneas en que consistió el SERVICIO realizado al Socio Comunitario", c.TEXTO_LARGO),
            pregunta("Semestre en el que trabajó con el SC", c.ALTERNATIVA_UNICA, [
                "Otoño", "Primavera", "Ambos"
            ]),
            pregunta("Evalúe al Socio Comunitarios (En cuanto a su recomendación para volver a trabajar con él)", c.ESCALA, estilo="estrellas", minimo=1, maximo=5),
            pregunta("Déjenos su comentario acerca del Socio Comunitario", c.TEXTO_LARGO),
        ]),
    ],
}
