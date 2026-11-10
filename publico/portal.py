"""
Qué muestra el portal público (RF-PUB-01, HU-10).

El Coordinador enciende o apaga cada bloque del portal y, dentro de cada uno,
elige qué datos se ven. Aquí solo hay datos agregados: RUT, correos,
teléfonos, direcciones y nombres de personas nunca son una opción
(RNF-PRI-01), así que no se pueden activar por error.

La configuración se guarda en ConfiguracionPortal.opciones_json con la forma
{"mapa": {"activo": True, "opciones": ["proyectos", ...]}, ...}. Lo que no
esté guardado se muestra, para que el portal no cambie hasta que el
Coordinador decida otra cosa.
"""

from django.db import transaction
from django.utils import timezone

from auditoria.services import registrar_auditoria

from .models import ConfiguracionPortal


# (clave, título, descripción, icono, [(grupo, [(opción, etiqueta)])])
BLOQUES = [
    (
        "mapa", "Mapa de impacto territorial",
        "Socios y proyectos por comuna. Nunca direcciones ni contactos.",
        "bi-geo-alt",
        [
            ("Vistas del mapa", [
                ("proyectos", "Proyectos por comuna"),
                ("socios", "Socios comunitarios por comuna"),
            ]),
            ("Datos al hacer clic en una comuna", [
                ("participaciones", "N° de participaciones"),
                ("carreras", "Carreras"),
                ("anios", "Años"),
            ]),
            ("Cifras bajo el mapa", [
                ("cifra_socios", "Socios comunitarios"),
                ("cifra_participaciones", "Participaciones"),
                ("cifra_comunas", "Comunas alcanzadas"),
                ("cifra_estudiantes", "Estudiantes participantes"),
            ]),
        ],
    ),
    (
        "cifras", "Cifras macro del programa",
        "Totales agregados del programa A+S.",
        "bi-bar-chart",
        [
            ("Cifras que se muestran", [
                ("asignaturas", "Asignaturas A+S"),
                ("carreras", "Carreras participantes"),
                ("facultades", "Facultades involucradas"),
                ("socios", "Socios comunitarios"),
            ]),
        ],
    ),
    (
        "catalogo", "Catálogo de proyectos A+S",
        "Tarjetas por año y servicio realizado. Sin nombres de socios ni de personas.",
        "bi-grid-3x2-gap",
        [
            ("Datos de cada tarjeta", [
                ("socios", "N° de socios"),
                ("carrera", "Carrera"),
                ("asignatura", "Asignatura"),
                ("comunas", "Comunas"),
                ("tipos", "Tipos de socio"),
            ]),
        ],
    ),
    (
        "noticias", "Noticias",
        "Últimas noticias publicadas por Coordinación.",
        "bi-newspaper",
        [],
    ),
    (
        "repositorio", "Repositorio público A+S",
        "Botón y página con los documentos marcados como Públicos en la pestaña Documentos.",
        "bi-folder2-open",
        [],
    ),
]

# Grupos donde debe quedar al menos una opción marcada para que el bloque tenga sentido.
MINIMO_UNA = {("mapa", "Vistas del mapa")}


def _opciones_de(grupos):
    return [clave for _, opciones in grupos for clave, _ in opciones]


def _por_defecto():
    return {
        clave: {"activo": True, "opciones": _opciones_de(grupos)}
        for clave, _, _, _, grupos in BLOQUES
    }


def _normalizar(guardado):
    """Mezcla lo guardado con los valores por defecto y descarta claves desconocidas."""
    resultado = _por_defecto()
    for clave, _, _, _, grupos in BLOQUES:
        datos = (guardado or {}).get(clave)
        if not isinstance(datos, dict):
            continue
        validas = _opciones_de(grupos)
        resultado[clave]["activo"] = bool(datos.get("activo", True))
        if isinstance(datos.get("opciones"), list):
            resultado[clave]["opciones"] = [o for o in validas if o in datos["opciones"]]
    return resultado


def obtener_configuracion():
    """Fila única de configuración (la crea vacía si no existe)."""
    configuracion, _ = ConfiguracionPortal.objects.get_or_create(pk=1)
    return configuracion


def configuracion_portal():
    """
    {bloque: {"activo": bool, "opciones": set, "<opcion>": bool}} listo para
    las vistas y plantillas: portal.mapa.activo, portal.cifras.carreras, etc.
    """
    configuracion = ConfiguracionPortal.objects.filter(pk=1).first()
    datos = _normalizar(configuracion.opciones_json if configuracion else None)
    portal = {}
    for clave, _, _, _, grupos in BLOQUES:
        bloque = datos[clave]
        marcadas = set(bloque["opciones"])
        portal[clave] = {"activo": bloque["activo"], "opciones": marcadas}
        for opcion in _opciones_de(grupos):
            portal[clave][opcion] = bloque["activo"] and opcion in marcadas
    return portal


def bloques_para_formulario(configuracion=None):
    """Bloques con sus grupos y el estado actual, para la pantalla del Coordinador."""
    datos = _normalizar((configuracion or obtener_configuracion()).opciones_json)
    bloques = []
    for clave, titulo, descripcion, icono, grupos in BLOQUES:
        marcadas = set(datos[clave]["opciones"])
        total = len(_opciones_de(grupos))
        bloques.append({
            "clave": clave,
            "titulo": titulo,
            "descripcion": descripcion,
            "icono": icono,
            "activo": datos[clave]["activo"],
            "marcadas": len(marcadas),
            "total": total,
            "grupos": [
                {
                    "titulo": grupo,
                    "minimo_una": (clave, grupo) in MINIMO_UNA,
                    "opciones": [
                        {"clave": opcion, "etiqueta": etiqueta, "marcada": opcion in marcadas}
                        for opcion, etiqueta in opciones
                    ],
                }
                for grupo, opciones in grupos
            ],
        })
    return bloques


def leer_formulario(post):
    """
    Lee el POST de la pantalla: "<bloque>__activo" y "<bloque>__<opcion>".
    Devuelve (opciones_json, errores).
    """
    opciones_json = {}
    errores = []
    for clave, titulo, _, _, grupos in BLOQUES:
        activo = post.get(f"{clave}__activo") == "on"
        marcadas = [o for o in _opciones_de(grupos) if post.get(f"{clave}__{o}") == "on"]
        if activo:
            for grupo, opciones in grupos:
                if (clave, grupo) in MINIMO_UNA and not any(o in marcadas for o, _ in opciones):
                    errores.append(f"{titulo}: marca al menos una opción en «{grupo}».")
        opciones_json[clave] = {"activo": activo, "opciones": marcadas}
    return opciones_json, errores


def guardar_configuracion(opciones_json, request):
    """Guarda la configuración y deja el cambio en auditoría (RNF-AUD-01)."""
    with transaction.atomic():
        configuracion = obtener_configuracion()
        anteriores = _normalizar(configuracion.opciones_json)
        nuevas = _normalizar(opciones_json)
        configuracion.opciones_json = nuevas
        configuracion.actualizado_por = request.user
        configuracion.fecha_actualizacion = timezone.now()
        configuracion.save()
        if anteriores != nuevas:
            registrar_auditoria(
                request=request,
                entidad="ConfiguracionPortal",
                entidad_id=configuracion.pk,
                accion="CONFIGURAR_PORTAL_PUBLICO",
                valores_anteriores=anteriores,
                valores_nuevos=nuevas,
            )
    return configuracion
