"""
Socio nuevo en el Registro de equipo (actividad 13 de la Ruta, RF-SC-04).

El estudiante registra en un solo formulario su equipo y el socio con el que
trabajará. Si el socio no está en el listado, se piden los mismos datos del
"Registro de Socios Comunitarios" de la Coordinación (organización,
representante, cargo, teléfono, correo, comuna, dirección y clasificación)
y se guardan normalizados en el socio y su contacto principal, no como texto
suelto de un formulario. Así el socio se ingresa una sola vez y llega al
mapa, los indicadores, el catálogo y el Acuerdo (actividad 11).

Lo que se completa durante el semestre (beneficiarios, servicio, evaluación
y comentario: preguntas 18 a 22) va en la participación del equipo; ver
proyectos.trabajo_socio.
"""

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from core.textos import nombre_persona
from encuestas import formatos
from socios.comunas import buscar_comuna
from socios.models import ClasificacionSocio, ContactoSocio, SocioComunitario

CAMPOS = [
    ("socio_representante", "el representante"),
    ("socio_cargo", "el cargo del representante"),
    ("socio_telefono", "el teléfono"),
    ("socio_correo", "el correo"),
    ("socio_comuna", "la comuna"),
    ("socio_direccion", "la dirección"),
    ("socio_clasificacion", "la clasificación"),
]


def clasificaciones():
    return ClasificacionSocio.objects.filter(activo=True).exclude(nombre__iexact="Otras").order_by("nombre")


def leer(post):
    """Datos del socio nuevo tal como se escribieron (para volver a mostrarlos)."""
    datos = {campo: formatos.ordenado(post.get(campo, "")) for campo, _ in CAMPOS}
    datos["socio_clasificacion_otra"] = formatos.ordenado(post.get("socio_clasificacion_otra", ""))
    return datos


def validar(datos):
    """Devuelve (limpios, errores). limpios trae los objetos listos para crear el socio."""
    errores = []
    for campo, nombre in CAMPOS:
        if not datos.get(campo):
            errores.append(f"Socio nuevo: falta {nombre}.")
    limpios = {}

    if datos.get("socio_telefono"):
        try:
            limpios["telefono"] = formatos.telefono(datos["socio_telefono"])
        except ValidationError as error:
            errores.append(f"Socio nuevo: {error.messages[0]}")
    if datos.get("socio_correo"):
        try:
            validate_email(datos["socio_correo"])
            limpios["correo"] = datos["socio_correo"].lower()
        except ValidationError:
            errores.append("Socio nuevo: el correo no es válido.")
    if datos.get("socio_comuna"):
        limpios["comuna"] = buscar_comuna(datos["socio_comuna"])
        if limpios["comuna"] is None:
            errores.append("Socio nuevo: elige la comuna de la lista (escribe las primeras letras).")

    eleccion = datos.get("socio_clasificacion")
    if eleccion == "otra":
        if not datos.get("socio_clasificacion_otra"):
            errores.append("Socio nuevo: escribe cuál es la clasificación.")
        limpios["clasificacion"] = ClasificacionSocio.objects.filter(nombre__iexact="Otras").first()
        limpios["clasificacion_otra"] = datos.get("socio_clasificacion_otra")[:120] or None
    elif eleccion:
        limpios["clasificacion"] = clasificaciones().filter(pk=eleccion if eleccion.isdigit() else None).first()
        limpios["clasificacion_otra"] = None
        if limpios["clasificacion"] is None:
            errores.append("Socio nuevo: la clasificación elegida no es válida.")

    limpios["representante"] = nombre_persona(datos.get("socio_representante", ""))[:180]
    limpios["cargo"] = datos.get("socio_cargo", "")[:120] or None
    limpios["direccion"] = datos.get("socio_direccion", "")[:255] or None
    return limpios, errores


def crear(nombre, limpios):
    """Crea el socio provisional y su contacto principal (dentro de la transacción del registro)."""
    socio = SocioComunitario.objects.create(
        nombre_organizacion=nombre,
        clasificacion=limpios.get("clasificacion"),
        clasificacion_otra=limpios.get("clasificacion_otra"),
        comuna=limpios.get("comuna"),
        direccion_exacta=limpios.get("direccion"),
        estado_revision="RECIBIDO",
        es_provisional=True,
        activo=True,
        fecha_creacion=timezone.now(),
    )
    ContactoSocio.objects.create(
        socio=socio,
        nombre=limpios["representante"] or nombre,
        cargo=limpios.get("cargo"),
        correo=limpios.get("correo"),
        telefono=limpios.get("telefono"),
        es_principal=True,
        activo=True,
    )
    return socio
