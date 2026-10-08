"""
Carga la Ficha de Inscripción de Emprendedores como un formulario configurable
con pestañas por programa (HU-09, RF-FOR-03).

Junta en un solo formulario las tres fichas que hoy se envían por separado
(knowledge/Forms preguntas.txt): Investigación de Mercados, Consultoría
Empresas y Gestión de Procesos de Negocios. Las preguntas y opciones se
copiaron tal como están en los forms; las comunes se responden una vez y las
de cada programa aparecen solo con su pestaña.

Es idempotente: si el formulario ya existe, no hace nada.

    python manage.py cargar_ficha_emprendedores
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from academico.models import Carrera
from encuestas import constantes as c
from encuestas import services
from encuestas.models import (
    BloqueFormulario,
    FormularioPlantilla,
    FormularioVersion,
    OpcionPregunta,
    PreguntaFormulario,
)

CODIGO = "FICHA_EMPRENDEDORES"

INV_MERCADOS = "INV_MERCADOS"
CONSULTORIA = "CONSULTORIA_EMPRESAS"
GESTION_PROCESOS = "GESTION_PROCESOS"

# Textos de invitación copiados de cada forms (sin el aviso automático de Microsoft Forms).
INTRO_INV_MERCADOS = 'La Universidad Autónoma de Chile, a través de la asignatura Investigación de Mercados de la carrera de Ingeniería Comercial, invita a emprendedores y pequeñas empresas a participar en un proceso de investigación de mercado aplicada, orientada a responder preguntas concretas sobre su producto, servicio o negocio. Este estudio consiste en una investigación cuantitativa de una medición, desarrollada principalmente mediante encuestas, que permitirá obtener información relevante para comprender mejor a sus clientes y apoyar la toma de decisiones de su emprendimiento. El trabajo será realizado por estudiantes de la carrera, bajo la supervisión directa de un profesor, quien velará por el correcto desarrollo de todas las etapas del proceso investigativo. Entre los temas que se pueden abordar se encuentran, por ejemplo:\nConocimiento y posicionamiento de marca\nMotivaciones de compra de los clientes\nEvaluación de calidad de servicio\nComparación con competidores\nPercepción de productos o servicios\nPre testeo de piezas publicitarias\nOtras preguntas relevantes para su negocio\nPara que la investigación sea exitosa, será importante contar con su colaboración y con información básica de su emprendimiento, lo que permitirá evaluar la factibilidad del estudio. Esta iniciativa se desarrolla bajo la metodología Aprendizaje + Servicio (A+S), mediante la cual los estudiantes aplican sus conocimientos en situaciones reales, generando a la vez un aporte concreto a emprendedores de la comunidad. 🕒 Este formulario le tomará aproximadamente 4 minutos en completarse. 🔒 Toda la información entregada será tratada con estricta confidencialidad y utilizada únicamente con fines académicos. Su participación es muy importante, ya que contribuye tanto a la formación de nuestros estudiantes como al fortalecimiento de los emprendimientos participantes.'
INTRO_CONSULTORIA = 'La Universidad Autónoma, a través de la cátedra Consultoría Empresas de la carrera de Ingeniería Civil Industrial pone a disposición de quienes lo pudieran requerir la oferta de una asesoría integral con alumnos de 4to año de la carrera dirigidos por 2 docentes de la universidad,\n\nProductos a entregar:\n\nLas beneficiarias contarán con un informe en el ámbito de desarrollo de la consultoría, donde se detalla el trabajo de análisis y las propuestas de acuerdo a las necesidades de cada negocio:\n\nLos temas a tratar se indican más abajo\n\nPerfil de Empresas:\nMicro y pequeña empresa.\n\nCaracterística de las organizaciones:\nFormalizadas, con un tiempo de facturación de al menos 2 años.\n\nTiempo requerido para reuniones de trabajo (alumnos y beneficiaria):\nAl menos 3 sesiones de 90 minutos como mínimo entre agosto y noviembre 2025  (presentación, recopilación de antecedentes, borrador de avance) pueden ser presencial u online. La oportunidad y número de sesiones se pactan directamente con los estudiantes de comun acuerdo.\n\nEntrega del Informe Final\nEn forma presencial durante el mes de Noviembre 2025\n\nUsted puede elegir los temas que más le interesen,  los profesores decidirán cual de ellos  es el que más se acerca a sus necesidades actuales para llevarlo a cabo.\n\nLa información por usted entregada durante el proceso será de carácter estrictamente confidencial.\nTrabajamos utilizando una metodología llamada Aprendizaje + Servicio (A+S) donde los estudiantes de la Universidad Autónoma aplican sus conocimiento en base a casos reales entregando un servicio de calidad, por lo que su participación en este programa es muy importante para nosotros.\n\nLos emprendedores seleccionados se citarán a una reunión OnLines durante el mes de agosto para resolver dudas e indicar detalles de la intervención\nSe invitará a los emprendedores seleccionados a una presentación al final del semestre (fines de noviembre) a la universidad, donde podrán compartir con los docentes y profesores de la carrera.'
INTRO_GESTION_PROCESOS = 'Las organizaciones, en su proceso de crecimiento y mejora continua, buscan optimizar la forma en que desarrollan sus actividades. Muchas veces, ordenar y revisar los procesos de trabajo permite ahorrar tiempo, reducir errores y mejorar el servicio a los clientes. En este contexto, la Escuela de Ingeniería de Control y Gestión de la Universidad Autónoma de Chile invita a empresas, emprendedores y organizaciones a participar en una Clínica Empresarial de Gestión de Procesos, donde estudiantes trabajarán en el análisis y mejora de procesos operativos y de negocio. Durante esta experiencia, un equipo de estudiantes —guiados por un profesor— desarrollará un diagnóstico y propuestas de mejora orientadas a optimizar el funcionamiento de su organización. El trabajo podrá considerar, entre otros aspectos:\nLevantamiento de procesos y detección de brechas, para comprender cómo se desarrollan actualmente las actividades del negocio.\nAnálisis y propuestas de mejora de procesos, orientadas a hacer el trabajo más eficiente.\nIdentificación de puntos críticos del proceso, donde sea necesario revisar errores, tiempos o costos.\nPropuestas prácticas para simplificar y mejorar los procesos, buscando que sean más claros, rápidos y ordenados.\nDiseño de indicadores simples, que permitan monitorear el desempeño y apoyar la toma de decisiones.\nBeneficios de participar Las organizaciones participantes podrán obtener:\nIdentificación de pérdidas de tiempo o reprocesos en sus procesos actuales.\nDetección de posibles errores operativos y oportunidades de mejora.\nPropuestas para mejorar tiempos de atención o eficiencia operativa.\nIndicadores simples para evaluar si los procesos están mejorando.\nUn informe claro y aplicable con recomendaciones de mejora.\nEsta iniciativa se desarrolla bajo la metodología Aprendizaje + Servicio (A+S), mediante la cual los estudiantes de la Universidad Autónoma aplican sus conocimientos en situaciones reales, generando a la vez un aporte concreto a empresas y organizaciones de la comunidad. 🕒 Este formulario le tomará aproximadamente 4 minutos en completarse. 🔒 Toda la información entregada será tratada con estricta confidencialidad y utilizada únicamente con fines académicos. Su participación es muy valiosa, ya que contribuye tanto a la formación de nuestros estudiantes como al fortalecimiento de las organizaciones participantes.'

PROGRAMAS = [
    # (valor, texto de la pestaña, palabra para buscar la carrera en el catálogo)
    (INV_MERCADOS, "Investigación de Mercados (Ingeniería Comercial)", "Comercial"),
    (CONSULTORIA, "Consultoría Empresas (Ingeniería Civil Industrial)", "Civil Industrial"),
    (GESTION_PROCESOS, "Gestión de Procesos de Negocios (Ingeniería de Control y Gestión)", "Control"),
]

TODOS = None  # sin restricción: la opción se muestra en los tres programas
SIN_CONSULTORIA = [INV_MERCADOS, GESTION_PROCESOS]

# Cada sección: (título, texto, programas en que se muestra o None, preguntas).
# Cada pregunta: (texto, tipo, obligatoria, opciones, config).
# Cada opción: (texto, programas o None, es_otras).
SECCIONES = [
    ("Datos de contacto", "", None, [
        ("Nombre Completo", c.TEXTO_CORTO, True, [], {"dato_respondente": "nombre"}),
        ("RUT", c.RUT, True, [], {"dato_respondente": "rut"}),
        ("Correo electrónico de contacto", c.CORREO, True, [], {"dato_respondente": "correo"}),
        ("Telefono de Contacto +569...", c.TEXTO_CORTO, True, [], {"ayuda": "Ejemplo: +56 9 1234 5678"}),
        ("Nombre de su emprendimiento", c.TEXTO_CORTO, True, [], {}),
        ("Producto o servicio que comercializa", c.TEXTO_CORTO, True, [], {}),
    ]),
    ("Formalización", "", SIN_CONSULTORIA, [
        ("Está Formalizado?", c.ALTERNATIVA_UNICA, True, [
            ("Si", TODOS, False),
            ("No", TODOS, False),
            ("En Proceso de Formalización", TODOS, False),
        ], {}),
    ]),
    ("Su emprendimiento", "", None, [
        ("Rubro (Alimentación, Comercio, Servicios, etc.)", c.TEXTO_CORTO, True, [], {}),
        ("Antiguedada de su emprendimiento", c.ALTERNATIVA_UNICA, True, [
            ("Menos de 1 año", SIN_CONSULTORIA, False),
            ("Entre 1 y 2 años", TODOS, False),
            ("Más de 2 años", TODOS, False),
        ], {}),
        ("Indiquenos cuantas personas trabajan con usted", c.ALTERNATIVA_UNICA, True, [
            ("Solo yo", SIN_CONSULTORIA, False),
            ("2 persona", TODOS, False),
            ("3 personas", TODOS, False),
            ("Más de 3 personas", TODOS, False),
            ("Otras", [CONSULTORIA], True),
        ], {}),
        ("Favor indiquemos a que Centro de Negocios de Sercotec esta asociado, si es que lo esta.",
         c.TEXTO_CORTO, False, [], {}),
        ("Favor indíquenos el nombre del  ASESOR del Centro de Negocios Sercotec con que está trabajando.",
         c.TEXTO_CORTO, False, [], {}),
        ("Favor indiquenos el correo electrónico de su asesor Sercotec para invitarlo a una primera reunión junto con usted",
         c.CORREO, False, [], {}),
    ]),
    ("Temas de apoyo", "", [INV_MERCADOS], [
        ("En que otros temas podríamos brindarle apoyo con los alumnos y profesores de la Facultad de Administración y Negocios de la Universidad Autónoma",
         c.TEXTO_LARGO, False, [], {}),
    ]),
    ("Temas de apoyo", "", [CONSULTORIA], [
        ("En qué temas  de los indicados  podríamos brindarle apoyo con los alumnos y profesores de la Facultad de Ingeniería de la Universidad Autónoma (Se permite indicar más de uno)",
         c.SELECCION_MULTIPLE, True, [
            ("Consultoría en Gestión de Inventarios", TODOS, False),
            ("Consultoría Financiera, Costos, flujos, indicadores, etc.", TODOS, False),
            ("Consultoría de Recursos Humanos y Desarrollo Organizacional: (Reclutamiento y selección de personal, Desarrollo organizacional, Evaluación del desempeño, Capacitación, etc)", TODOS, False),
            ("Consultoría en Propuestas de productos/servicios, mejoras, nuevos productos, etc.", TODOS, False),
            ("Consultoría de Operaciones (optimización de Procesos, Gestión de la cadena de suministros, Control de calidad, Mejora continua)", TODOS, False),
            ("Realizar un Estudio de Mercado en la localidad donde se encuentre el emprendedor", TODOS, False),
            ("Otras", TODOS, True),
        ], {}),
        ("Le agradeceremos indicarnos dirección de su página web y/o redes sociales si  las tiene (Instagram, X u otra)",
         c.TEXTO_CORTO, False, [], {}),
        ("En este espacio, nos puede indicar algún comentario y/o requerimiento especial que necesite. Horarios para comunicarse con Ud. Otros temas de su interés, etc.",
         c.TEXTO_LARGO, False, [], {}),
    ]),
    ("Temas de apoyo", "", [GESTION_PROCESOS], [
        ("En qué otros temas podríamos brindarle apoyo con los alumnos y profesores de la Universidad",
         c.SELECCION_MULTIPLE, True, [
            ("Investigación de Mercados asociada a su emprendimiento en partícular", TODOS, False),
            ("Asesoría integral (Finanzas, Marketing, Recursos Humanos, etc)", TODOS, False),
            ("Confeccionar su página Web o Sitio Web", TODOS, False),
            ("Innovación asociada a su emprendimiento", TODOS, False),
            ("Asesoría en Sostenibilidad", TODOS, False),
            ("Resolución de problemas técnicos, con ingenieros", TODOS, False),
            ("Asesoría en etiquetado de productos alimenticios", TODOS, False),
            ("Otras", TODOS, True),
        ], {}),
    ]),
]

# Sección con el texto de invitación de cada programa, justo bajo las pestañas.
INTROS = [
    ("Ficha de Inscripción Emprendedores Investigación de Mercados", INTRO_INV_MERCADOS, INV_MERCADOS),
    ("Ficha Inscripción Emprendedores Programa Consultoría Empresas 2026 Ing. Civil Industrial", INTRO_CONSULTORIA, CONSULTORIA),
    ("Ficha de Inscripción en Programa de Gestión de Procesos de Negocios 2026", INTRO_GESTION_PROCESOS, GESTION_PROCESOS),
]


class Command(BaseCommand):
    help = "Carga la Ficha de Inscripción de Emprendedores con pestañas por programa (HU-09)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sin-publicar", action="store_true",
            help="Deja el formulario en borrador en vez de publicarlo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if FormularioPlantilla.objects.filter(codigo=CODIGO).exists():
            self.stdout.write(self.style.WARNING("La ficha de emprendedores ya existe. No se cambió nada."))
            return

        plantilla = FormularioPlantilla.objects.create(
            codigo=CODIGO,
            titulo="Ficha de Inscripción de Emprendedores A+S",
            descripcion=(
                "Seleccione el programa al que desea inscribirse. "
                "Se mostrarán la información y las preguntas de ese programa."
            ),
            proceso="INSCRIPCION_EMPRENDEDORES",
            activo=True,
        )
        version = FormularioVersion.objects.create(
            plantilla=plantilla,
            numero_version=1,
            estado=c.BORRADOR,
            contexto_tipo="EMPRENDEDOR",
            fecha_creacion=timezone.now(),
        )

        orden_bloque = 1
        bloque_programa = BloqueFormulario.objects.create(
            formulario_version=version, titulo="Programa", orden=orden_bloque,
        )
        selector = PreguntaFormulario.objects.create(
            version=version,
            bloque=bloque_programa,
            texto="Seleccione el programa al que desea inscribirse",
            tipo=c.SELECTOR_PROGRAMA,
            obligatoria=True,
            orden=1,
        )
        datos_opciones = {}
        for orden, (valor, texto, palabra) in enumerate(PROGRAMAS, start=1):
            OpcionPregunta.objects.create(
                pregunta=selector, texto=texto, valor=valor, orden=orden, es_otras=False,
            )
            carrera = Carrera.objects.filter(nombre__icontains=palabra).order_by("id").first()
            if carrera:
                datos_opciones[valor] = {"carrera_id": carrera.id}
        if datos_opciones:
            selector.configuracion_json = {"opciones": datos_opciones}
            selector.save(update_fields=["configuracion_json"])

        def regla(programas):
            return {"pregunta": selector.id, "valores": list(programas)} if programas else None

        for titulo, texto, valor in INTROS:
            orden_bloque += 1
            BloqueFormulario.objects.create(
                formulario_version=version, titulo=titulo, descripcion=texto,
                orden=orden_bloque, regla_visibilidad_json=regla([valor]),
            )

        total_preguntas = 1
        for titulo, texto, programas, preguntas in SECCIONES:
            orden_bloque += 1
            bloque = BloqueFormulario.objects.create(
                formulario_version=version, titulo=titulo, descripcion=texto or None,
                orden=orden_bloque, regla_visibilidad_json=regla(programas),
            )
            for orden, (texto_pregunta, tipo, obligatoria, opciones, config) in enumerate(preguntas, start=1):
                pregunta = PreguntaFormulario.objects.create(
                    version=version, bloque=bloque, texto=texto_pregunta, tipo=tipo,
                    obligatoria=obligatoria, orden=orden, configuracion_json=dict(config) or None,
                )
                total_preguntas += 1
                usados = set()
                reglas_opciones = {}
                for orden_opcion, (texto_opcion, programas_opcion, es_otras) in enumerate(opciones, start=1):
                    opcion = OpcionPregunta.objects.create(
                        pregunta=pregunta, texto=texto_opcion,
                        valor=services.valor_desde_texto(texto_opcion, usados),
                        orden=orden_opcion, es_otras=es_otras,
                    )
                    if programas_opcion:
                        reglas_opciones[opcion.valor] = regla(programas_opcion)
                if reglas_opciones:
                    pregunta.configuracion_json = {**(pregunta.configuracion_json or {}), "visibilidad_opciones": reglas_opciones}
                    pregunta.save(update_fields=["configuracion_json"])

        mensaje = f"Ficha de emprendedores creada: {orden_bloque} secciones y {total_preguntas} preguntas."
        if options["sin_publicar"]:
            self.stdout.write(self.style.SUCCESS(mensaje + " Quedó en borrador."))
            return
        enlace = services.publicar(version)
        self.stdout.write(self.style.SUCCESS(mensaje))
        self.stdout.write(f"Enlace público: /formularios/f/{enlace.token}/")
