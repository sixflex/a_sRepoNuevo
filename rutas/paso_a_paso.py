"""
Ruta del Docente paso a paso (ficha única del proyecto A+S).

El docente ve sus actividades agrupadas por etapa y solo la etapa en curso
abierta. Cada actividad tiene una sola acción principal (llenar el
formulario ya precargado, registrar la reflexión, mostrar el QR, subir la
evidencia...) y un "¿Cómo se hace?" con el detalle. Las etapas no se
bloquean: el docente puede abrir cualquiera (RN-13).

Las acciones se eligen por el orden de la actividad, igual que el resto de
la Ruta (Ruta docente.txt), y los formularios por su código: si la
actividad no tiene un formulario vinculado en la BD se usa la última
versión publicada de ese código, así no hace falta tocar la Ruta cargada.
"""

from django.db.models import Count, Q
from django.urls import reverse

from core.qr import qr_base64
from encuestas.definiciones.registro_reflexion import CODIGO as CODIGO_REFLEXION
from encuestas.definiciones.registro_reflexion import DINAMICAS, MOMENTO_POR_ORDEN
from encuestas.models import FormularioVersion, RespuestaOpcion
from encuestas import precarga

from .services import obtener_o_crear_enlace_seccion, url_recurso

# Orden de la actividad -> código del formulario que se llena en ella.
FORMULARIO_POR_ORDEN = {
    5: precarga.FORMULARIO_PROYECTO,
    11: precarga.FORMALIZACION_ACUERDOS,
    12: CODIGO_REFLEXION,
    13: "REGISTRO_SOCIO_COMUNITARIO_AS_2026",
    15: CODIGO_REFLEXION,
    17: CODIGO_REFLEXION,
    23: precarga.RESUMEN_IMPLEMENTACION,
}

# Lo que se ve bajo el nombre: qué hacer, en una línea.
QUE_HACER = {
    5: "Llena el formulario del proyecto. Los datos de la sección ya vienen escritos.",
    9: "Arma la pauta de evaluación y súbela aquí.",
    10: "Si un grupo la necesita, pide la carta a Coordinación.",
    11: "Llena el acuerdo de cada grupo, imprímelo, que lo firmen todos y sube el escaneado.",
    12: "Elige una de las dinámicas sugeridas, hazla en clase y registra cuál hiciste.",
    13: "Muestra el QR: un estudiante por grupo registra a su socio.",
    15: "Elige una de las dinámicas sugeridas, hazla en clase y registra cuál hiciste.",
    16: "Sube fotos, productos y otros respaldos del servicio.",
    17: "Elige una de las dinámicas sugeridas, hazla en clase y registra cuál hiciste.",
    19: "Proyecta el QR para que estudiantes y docentes respondan la encuesta.",
    22: "Sube la planilla de notas, los acuerdos firmados y las fotos.",
    23: "Llena el resumen final. Lo que el sistema ya sabe viene escrito.",
}

# Actividades donde el cliente pide un archivo (reunión 10-11-2026).
EVIDENCIA_PEDIDA = {
    9: "Sube el instrumento de evaluación.",
    11: "Sube el acuerdo firmado de cada grupo (uno por grupo).",
    16: "Sube las fotos y productos.",
    22: "Sube la planilla de notas, los acuerdos firmados y las fotos.",
}

TEXTO_BOTON = {
    5: ("Llenar formulario", "bi-pencil-square"),
    11: ("Llenar acuerdo", "bi-pencil-square"),
    12: ("Registrar reflexión", "bi-journal-check"),
    15: ("Registrar reflexión", "bi-journal-check"),
    17: ("Registrar reflexión", "bi-journal-check"),
    23: ("Llenar resumen", "bi-pencil-square"),
}

NOTA_PRECARGA = {
    5: "Docente, asignatura, carrera y grupos ya vienen llenos.",
    11: "Docente y asignatura ya vienen llenos.",
    23: "Tus datos, la asignatura y los totales de estudiantes y socios ya vienen llenos.",
}


def _version_formulario(ruta_actividad, cache):
    codigo = FORMULARIO_POR_ORDEN.get(ruta_actividad.orden)
    vinculada = ruta_actividad.formulario_version
    if vinculada is not None and (codigo is None or vinculada.plantilla.codigo == codigo):
        return vinculada
    if codigo is None:
        return None
    if codigo not in cache:
        cache[codigo] = (
            FormularioVersion.objects
            .filter(plantilla__codigo=codigo, plantilla__activo=True, estado="PUBLICADA")
            .select_related("plantilla")
            .order_by("-numero_version", "-pk")
            .first()
        )
    return cache[codigo]


def _reflexiones_registradas(seccion):
    """{momento: cantidad de registros} de la sección."""
    filas = (
        RespuestaOpcion.objects
        .filter(
            respuesta_pregunta__respuesta__seccion=seccion,
            respuesta_pregunta__respuesta__version__plantilla__codigo=CODIGO_REFLEXION,
            opcion__valor__in=set(MOMENTO_POR_ORDEN.values()),
        )
        .values("opcion__valor")
        .annotate(n=Count("id"))
    )
    return {fila["opcion__valor"]: fila["n"] for fila in filas}


def _equipos(seccion):
    equipos = seccion.equipos.aggregate(
        total=Count("id", distinct=True),
        con_socio=Count(
            "id", distinct=True,
            filter=Q(participaciones_socios__fecha_fin__isnull=True, participaciones_socios__isnull=False),
        ),
    )
    return equipos["total"], equipos["con_socio"]


def preparar_actividades(request, seccion_ruta, actividades):
    """
    Agrega a cada actividad lo que muestra la Ruta paso a paso:
    accion (botón principal), que_hacer, nota_precarga, progreso,
    evidencia_pedida, qr (actividad 13) y los recursos de "¿Cómo se hace?".
    """
    seccion = seccion_ruta.seccion
    cache = {}
    grupos, grupos_con_socio = _equipos(seccion)
    reflexiones = _reflexiones_registradas(seccion)

    for actividad in actividades:
        ruta_actividad = actividad.ruta_actividad
        orden = ruta_actividad.orden
        actividad.url_recurso = url_recurso(actividad)
        actividad.que_hacer = QUE_HACER.get(orden)
        actividad.nota_precarga = NOTA_PRECARGA.get(orden)
        actividad.evidencia_pedida = EVIDENCIA_PEDIDA.get(orden)
        actividad.progreso = None
        actividad.accion = None
        actividad.qr = None
        actividad.enlace_formulario = None

        version = _version_formulario(ruta_actividad, cache)
        enlace = None
        if version is not None:
            enlace = obtener_o_crear_enlace_seccion(version, seccion, request.user)
        actividad.enlace_formulario = enlace

        if enlace is not None:
            url = reverse("encuestas:responder", args=[enlace.token])
            if orden == 13:
                absoluta = request.build_absolute_uri(url)
                actividad.qr = {"url": absoluta, "qr_base64": qr_base64(absoluta)}
                actividad.accion = {"texto": "Mostrar QR", "icono": "bi-qr-code", "colapsa": f"qr-{actividad.id}"}
            else:
                texto, icono = TEXTO_BOTON.get(orden, ("Llenar formulario", "bi-pencil-square"))
                actividad.accion = {"texto": texto, "icono": icono, "url": url, "nueva_pestana": True}
        elif orden == 10:
            actividad.accion = {
                "texto": "Pedir carta", "icono": "bi-envelope-paper",
                "url": reverse("cartas:listar_cartas_seccion_docente", args=[seccion.id]),
            }
        elif orden == 19 and actividad.url_recurso:
            actividad.accion = {
                "texto": "Mostrar QR de encuestas", "icono": "bi-qr-code",
                "url": actividad.url_recurso, "nueva_pestana": True,
            }
        elif orden == 1 and actividad.url_recurso:
            actividad.accion = {
                "texto": "Ir al curso", "icono": "bi-box-arrow-up-right",
                "url": actividad.url_recurso, "nueva_pestana": True,
            }
        elif actividad.evidencia_pedida:
            actividad.accion = {"texto": "Subir archivo", "icono": "bi-upload", "colapsa": f"como-{actividad.id}"}

        if orden == 11 and grupos:
            firmados = min(len(actividad.evidencias.all()), grupos)
            actividad.progreso = f"{firmados} de {grupos} grupos"
        elif orden == 13 and grupos:
            actividad.progreso = f"{grupos_con_socio} de {grupos} grupos"
        elif orden in MOMENTO_POR_ORDEN and reflexiones.get(MOMENTO_POR_ORDEN[orden]):
            actividad.progreso = "Registrada"

        actividad.dinamicas = DINAMICAS.get(MOMENTO_POR_ORDEN.get(orden), [])
        actividad.ejemplo_evidencia = "Ej.: Grupo 2" if orden == 11 else "Descripción (opcional)"

        # Lo que se ve en "¿Cómo se hace?": la descripción y los recursos.
        actividad.recurso_extra = (
            actividad.url_recurso
            if actividad.url_recurso and orden not in (1, 10, 13, 19)
            else None
        )
    return actividades


def armar_etapas(actividades):
    """
    Etapas en orden, con su avance. La etapa actual es la primera con una
    actividad obligatoria pendiente (o la última si todo está hecho).
    """
    etapas = []
    por_nombre = {}
    for actividad in actividades:
        nombre = actividad.ruta_actividad.etapa
        if nombre not in por_nombre:
            por_nombre[nombre] = {
                "nombre": nombre, "actividades": [], "hechas": 0,
                "obligatorias_pendientes": 0, "pendientes": [], "archivos": 0,
            }
            etapas.append(por_nombre[nombre])
        etapa = por_nombre[nombre]
        etapa["actividades"].append(actividad)
        etapa["archivos"] += len(actividad.evidencias.all())
        if actividad.completada_por_docente_id:
            etapa["hechas"] += 1
        elif actividad.ruta_actividad.es_obligatoria:
            etapa["obligatorias_pendientes"] += 1
            etapa["pendientes"].append(actividad)

    actual = next((e for e in etapas if e["obligatorias_pendientes"]), etapas[-1] if etapas else None)
    for numero, etapa in enumerate(etapas, start=1):
        etapa["numero"] = numero
        etapa["total"] = len(etapa["actividades"])
        etapa["completa"] = etapa["obligatorias_pendientes"] == 0
        etapa["actual"] = etapa is actual
    return etapas, actual
