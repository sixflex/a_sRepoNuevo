"""Valores fijos del módulo de formularios configurables (HU-09)."""

# Tipos de pregunta (RF-FOR-02). El valor se guarda en PreguntaFormulario.tipo.
TEXTO_CORTO = "TEXTO_CORTO"
TEXTO_LARGO = "TEXTO_LARGO"
NUMERO = "NUMERO"
FECHA = "FECHA"
CORREO = "CORREO"
RUT = "RUT"
ALTERNATIVA_UNICA = "ALTERNATIVA_UNICA"
SELECCION_MULTIPLE = "SELECCION_MULTIPLE"
LISTA = "LISTA"
ESCALA = "ESCALA"
ARCHIVO = "ARCHIVO"
SELECTOR_PROGRAMA = "SELECTOR_PROGRAMA"

# Nombres como los de Google o Microsoft Forms, para que el cambio sea familiar.
TIPOS_PREGUNTA = [
    (TEXTO_CORTO, "Respuesta corta"),
    (TEXTO_LARGO, "Párrafo"),
    (ALTERNATIVA_UNICA, "Opción única"),
    (SELECCION_MULTIPLE, "Casillas (varias respuestas)"),
    (LISTA, "Lista desplegable"),
    (ESCALA, "Calificación"),
    (FECHA, "Fecha"),
    (NUMERO, "Número"),
    (CORREO, "Correo electrónico"),
    (RUT, "RUT"),
    (ARCHIVO, "Carga de archivo"),
    (SELECTOR_PROGRAMA, "Pestañas de programa o carrera"),
]

# Ícono de Bootstrap Icons para cada tipo en el constructor.
ICONOS_TIPO = {
    TEXTO_CORTO: "bi-text-left",
    TEXTO_LARGO: "bi-text-paragraph",
    ALTERNATIVA_UNICA: "bi-ui-radios",
    SELECCION_MULTIPLE: "bi-ui-checks",
    LISTA: "bi-menu-button-wide",
    ESCALA: "bi-star-half",
    FECHA: "bi-calendar-event",
    NUMERO: "bi-123",
    CORREO: "bi-envelope-at",
    RUT: "bi-person-vcard",
    ARCHIVO: "bi-cloud-arrow-up",
    SELECTOR_PROGRAMA: "bi-segmented-nav",
}

NOMBRES_TIPO = dict(TIPOS_PREGUNTA)

# Tipos cuyas respuestas se eligen entre OpcionPregunta.
TIPOS_CON_OPCIONES = {ALTERNATIVA_UNICA, SELECCION_MULTIPLE, LISTA, SELECTOR_PROGRAMA}

# Tipos que pueden servir de condición en una regla de visibilidad
# (respuesta única y elegida de una lista cerrada).
TIPOS_CONDICIONANTES = {ALTERNATIVA_UNICA, LISTA, SELECTOR_PROGRAMA}

# Estados de FormularioVersion (RF-FOR-01).
BORRADOR = "BORRADOR"
PUBLICADA = "PUBLICADA"
CERRADA = "CERRADA"
ARCHIVADA = "ARCHIVADA"

ESTADOS_VERSION = [
    (BORRADOR, "Borrador"),
    (PUBLICADA, "Publicada"),
    (CERRADA, "Cerrada"),
    (ARCHIVADA, "Archivada"),
]

NOMBRES_ESTADO = dict(ESTADOS_VERSION)

# Datos del respondente que una pregunta puede alimentar en RespuestaFormulario.
DATOS_RESPONDENTE = [
    ("", "No"),
    ("nombre", "Nombre del respondente"),
    ("correo", "Correo del respondente"),
    ("rut", "RUT del respondente"),
]

# Escala por defecto: de 1 a 5 estrellas, como el forms del cliente.
ESCALA_MINIMO_DEFECTO = 1
ESCALA_MAXIMO_DEFECTO = 5
ESCALA_MAXIMO_PERMITIDO = 10

# Texto con que nace una pregunta agregada desde el constructor.
PREGUNTA_NUEVA = "Pregunta sin título"
OPCION_NUEVA = "Opción 1"

ORIGEN_ENLACE = "ENLACE"
ESTADO_REGISTRO_COMPLETO = "COMPLETO"
