"""Valores fijos del módulo de formularios configurables (HU-09)."""


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


TIPOS_CON_OPCIONES = {ALTERNATIVA_UNICA, SELECCION_MULTIPLE, LISTA, SELECTOR_PROGRAMA}



TIPOS_CONDICIONANTES = {ALTERNATIVA_UNICA, LISTA, SELECTOR_PROGRAMA}


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


DATOS_RESPONDENTE = [
    ("", "No"),
    ("nombre", "Nombre del respondente"),
    ("correo", "Correo del respondente"),
    ("rut", "RUT del respondente"),
]


ESCALA_MINIMO_DEFECTO = 1
ESCALA_MAXIMO_DEFECTO = 5
ESCALA_MAXIMO_PERMITIDO = 10


PREGUNTA_NUEVA = "Pregunta sin título"
OPCION_NUEVA = "Opción 1"

ORIGEN_ENLACE = "ENLACE"

ORIGEN_HISTORICO = "HISTORICO"
ESTADO_REGISTRO_COMPLETO = "COMPLETO"




TEMA_POR_DEFECTO = "rojo"
TEMAS = {
    "rojo": {"nombre": "Rojo UA", "base": "#C8232C", "hover": "#A71C23", "suave": "#FDEDEE", "rgb": "200, 35, 44"},
    "azul": {"nombre": "Azul", "base": "#1D4ED8", "hover": "#1E40AF", "suave": "#EFF6FF", "rgb": "29, 78, 216"},
    "verde": {"nombre": "Verde", "base": "#15803D", "hover": "#166534", "suave": "#F0FDF4", "rgb": "21, 128, 61"},
    "morado": {"nombre": "Morado", "base": "#6D28D9", "hover": "#5B21B6", "suave": "#F5F3FF", "rgb": "109, 40, 217"},
    "grafito": {"nombre": "Grafito", "base": "#374151", "hover": "#1F2937", "suave": "#F3F4F6", "rgb": "55, 65, 81"},
}


FONDO_EXTENSIONES = ("jpg", "jpeg", "png")
FONDO_MAX_MB = 5
