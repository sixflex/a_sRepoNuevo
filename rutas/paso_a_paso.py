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

from datetime import timedelta
from urllib.parse import quote

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from core.qr import qr_base64
from core.volver import con_volver
from socios.services import socios_elegidos_seccion
from encuestas.definiciones.registro_reflexion import CODIGO as CODIGO_REFLEXION
from encuestas.definiciones.registro_reflexion import DETALLE_DINAMICA, DINAMICAS, MOMENTO_POR_ORDEN
from encuestas.models import FormularioVersion, RespuestaOpcion
from encuestas import precarga

from . import acuerdo
from .services import formularios_qr_de_proceso, obtener_o_crear_enlace_seccion, url_recurso

# Actividades donde la Ruta de Jorge dice "contacte al Coordinador A+S"
# (1.2 reunión inicial, 1.3 charla, 2.1 reunión con socios, 2.4 instrumento):
# orden -> (texto del botón, asunto del correo).
CONTACTO_COORDINACION = {
    2: ("Escribir a Coordinación", "Reunión inicial A+S"),
    3: ("Invitar a Coordinación", "Charla A+S para mi curso"),
    6: ("Pedir reunión con socios a Coordinación", "Reunión con socios comunitarios en la Universidad"),
    9: ("Pedir apoyo a Coordinación", "Apoyo con el instrumento de evaluación A+S"),
}

# Días que queda abierto el registro de equipos al crearlo (igual que en proyectos).
DIAS_REGISTRO_EQUIPOS = 7

# Orden de la actividad -> código del formulario que se llena en ella.
FORMULARIO_POR_ORDEN = {
    5: precarga.FORMULARIO_PROYECTO,
    11: precarga.FORMALIZACION_ACUERDOS,
    12: CODIGO_REFLEXION,
    15: CODIGO_REFLEXION,
    17: CODIGO_REFLEXION,
    23: precarga.RESUMEN_IMPLEMENTACION,
}

# Lo que se ve bajo el nombre: qué hacer, en una línea.
QUE_HACER = {
    2: "Escríbele a Coordinación para agendar la visita a tu sala y recibir las instrucciones del período.",
    3: "Presenta A+S a tu curso. Si quieres, invita a Coordinación a dar la charla.",
    6: "Elige los socios para tu sección: son los que verán los estudiantes al registrar su equipo.",
    5: "Llena el formulario del proyecto. Los datos de la sección ya vienen escritos.",
    9: "Arma la pauta de evaluación y súbela aquí.",
    10: "Si un grupo la necesita, pide la carta a Coordinación o muestra el QR para que la pida un estudiante.",
    11: "Llena el acuerdo de cada grupo (viene con su socio y sus integrantes), descárgalo en PDF, imprímelo, que lo firmen todos y sube el escaneado.",
    12: "Elige una de las dinámicas sugeridas, hazla en clase y registra cuál hiciste.",
    13: "Muestra el QR: un estudiante por grupo inscribe a su equipo y a su socio. Durante el semestre vuelven al mismo enlace para contar el trabajo con el socio.",
    15: "Elige una de las dinámicas sugeridas, hazla en clase y registra cuál hiciste.",
    16: "Sube fotos, productos y otros respaldos del servicio.",
    17: "Elige una de las dinámicas sugeridas, hazla en clase y registra cuál hiciste.",
    19: "Proyecta el QR para que estudiantes y docentes respondan la encuesta.",
    21: "Las informas en el Resumen final (actividad 23): nota promedio A+S, promedio final del curso, estudiantes y reprobados. El porcentaje de reprobación lo calcula el portal.",
    22: "Tu carpeta se fue armando con lo que subiste en la Ruta. Revisa qué tiene y sube la planilla de notas: Coordinación la ve completa, no hay que enviarla por correo.",
    23: "Llena el resumen final. Lo que el sistema ya sabe viene escrito.",
}

# Actividades donde el cliente pide un archivo (reunión 10-11-2026).
EVIDENCIA_PEDIDA = {
    9: "Sube el instrumento de evaluación.",
    11: "Sube el acuerdo firmado de cada grupo (uno por grupo).",
    16: "Sube las fotos y productos.",
    22: "Sube la planilla de notas (lo demás ya está en la carpeta).",
}

TEXTO_BOTON = {
    5: ("Llenar formulario", "bi-pencil-square"),
    11: ("Llenar acuerdo", "bi-pencil-square"),
    12: ("Registrar reflexión", "bi-journal-check"),
    15: ("Registrar reflexión", "bi-journal-check"),
    17: ("Registrar reflexión", "bi-journal-check"),
    23: ("Llenar resumen", "bi-pencil-square"),
}

# Material de apoyo de la Ruta de la Coordinación (PDF interactivo de Jorge
# Reino): las tres reflexiones enlazan la misma propuesta de dinámicas.
MATERIAL_REFLEXION = [
    {"texto": "Propuesta de reflexiones (PDF)", "icono": "bi-file-earmark-pdf",
     "url": "https://drive.google.com/file/d/1WMAUxPFofsuq83kIBsDYFUiGGc43tmy7/view"},
    {"texto": "Presentación «Reflexión: una propuesta»", "icono": "bi-easel",
     "url": "https://docs.google.com/presentation/d/1LSSh6Qp5PtUXP6N1dEutekKVSj1nSWkW/edit"},
    {"texto": "Actividades de reflexión A+S (UC)", "icono": "bi-box-arrow-up-right",
     "url": "https://cddoc.uc.cl/programas/actividades-de-reflexion-as/"},
]
# La infografía de la carta (10) no va: explicaba el formulario de Microsoft,
# y la carta ahora se pide en el portal con el botón "Pedir carta".
MATERIAL_POR_ORDEN = {
    12: MATERIAL_REFLEXION,
    15: MATERIAL_REFLEXION,
    17: MATERIAL_REFLEXION,
}

NOTA_PRECARGA = {
    5: "Docente, asignatura, carrera y grupos ya vienen llenos.",
    11: "Docente, asignatura, el socio del grupo y sus integrantes ya vienen llenos.",
    23: "Tus datos, la asignatura, los totales, el tipo de socios, los beneficiarios que informaron los grupos y lo que escribiste del proyecto ya vienen llenos.",
}


def _publicada(codigo, cache):
    if codigo not in cache:
        cache[codigo] = (
            FormularioVersion.objects
            .filter(plantilla__codigo=codigo, plantilla__activo=True, estado="PUBLICADA")
            .select_related("plantilla")
            .order_by("-numero_version", "-pk")
            .first()
        )
    return cache[codigo]


def _version_formulario(ruta_actividad, cache):
    codigo = FORMULARIO_POR_ORDEN.get(ruta_actividad.orden)
    vinculada = ruta_actividad.formulario_version
    if vinculada is not None and (codigo is None or vinculada.plantilla.codigo == codigo):
        # Si el formulario tiene una versión más nueva publicada (al publicarla
        # la vinculada queda cerrada), la Ruta abre la vigente.
        return _publicada(vinculada.plantilla.codigo, cache) or vinculada
    if codigo is None:
        return None
    return _publicada(codigo, cache)


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


def _acuerdos_por_grupo(seccion, url):
    """Opciones del botón "Llenar acuerdo": una por grupo y una en blanco."""
    from proyectos.models import Equipo

    con_acuerdo = {r.equipo_id for r in acuerdo.acuerdos_de(seccion) if r.equipo_id}
    equipos = Equipo.objects.filter(seccion=seccion).con_socio_vigente().order_by("numero_grupo")
    opciones = [
        {
            "texto": f"Grupo {e.numero_grupo}" + (f" · {e.socio_vigente.nombre_organizacion}" if e.socio_vigente else ""),
            "url": f"{url}?equipo={e.id}",
            "listo": e.id in con_acuerdo,
        }
        for e in equipos
    ]
    if opciones:
        opciones.append({"texto": "Sin grupo (se llena a mano)", "url": url, "listo": False})
    return opciones


def _correo_coordinacion():
    """Correo del Coordinador A+S (el primero del grupo), o None."""
    from django.contrib.auth import get_user_model

    usuario = (
        get_user_model().objects.filter(groups__name="Coordinador", is_active=True)
        .filter(Q(correo_institucional__gt="") | Q(email__gt="")).order_by("id").first()
    )
    if usuario is None:
        return None
    return usuario.correo_institucional or usuario.email or None


def _mailto(correo, asunto, seccion):
    asunto = f"{asunto} · {seccion.asignatura.nombre} (NRC {seccion.nrc})"
    return f"mailto:{correo}?subject={quote(asunto)}"


def _carta_estudiantes(request, seccion, actividad):
    """
    QR para que un estudiante pida la carta (Ruta de Jorge, 2.5: "el
    formulario puede ser completado por un estudiante bajo su supervisión").
    El enlace de la sección se crea la primera vez, como el del registro.
    """
    from cartas.models import EnlaceSolicitudCarta

    enlace = (
        EnlaceSolicitudCarta.objects.filter(seccion=seccion, activo=True)
        .filter(Q(fecha_expiracion__isnull=True) | Q(fecha_expiracion__gt=timezone.now()))
        .order_by("-fecha_inicio", "-id").first()
    )
    if enlace is None:
        docente = getattr(request.user, "perfil_docente", None) or seccion.docentes.first()
        if docente is None:
            return False
        enlace = EnlaceSolicitudCarta.objects.create(
            seccion=seccion, creado_por_docente=docente, fecha_inicio=timezone.now(), activo=True,
        )
    url = request.build_absolute_uri(reverse("cartas:solicitar_carta_estudiante", args=[enlace.token]))
    actividad.qrs = [{
        "titulo": "Solicitud de Carta de Presentación",
        "ayuda": "Un estudiante del grupo escanea el QR y pide la carta; te llega a ti y a Coordinación para revisarla.",
        "url": url, "qr_base64": qr_base64(url),
    }]
    return True


def _registro_equipos(request, seccion, actividad):
    """
    QR del registro de equipos de la sección (actividad 13). Si la sección
    nunca lo habilitó se crea aquí, como los enlaces de los formularios; si
    el docente lo cerró, el QR sigue sirviendo a los equipos ya inscritos y
    se avisa cómo reabrirlo.
    """
    from proyectos.models import EnlaceRegistroEquipo

    enlace = EnlaceRegistroEquipo.objects.filter(seccion=seccion).order_by("-fecha_inicio", "-id").first()
    if enlace is None:
        docente = getattr(request.user, "perfil_docente", None) or seccion.docentes.first()
        if docente is None:
            return
        ahora = timezone.now()
        enlace = EnlaceRegistroEquipo.objects.create(
            seccion=seccion, creado_por_docente=docente, fecha_inicio=ahora,
            fecha_expiracion=ahora + timedelta(days=DIAS_REGISTRO_EQUIPOS), activo=True,
        )
    abierto = enlace.activo and (enlace.fecha_expiracion is None or enlace.fecha_expiracion > timezone.now())
    url = request.build_absolute_uri(reverse("proyectos:acceso_registro_equipos", args=[enlace.token]))
    ayuda = "Un estudiante por grupo escanea el QR e inscribe a su equipo y a su socio."
    if not abierto:
        ayuda = (
            "El registro está cerrado para equipos nuevos (ábrelo de nuevo en «Registro de equipos»); "
            "los equipos ya inscritos igual entran para contar su trabajo con el socio."
        )
    actividad.qrs = [{
        "titulo": "Registro de equipo y socio comunitario",
        "ayuda": ayuda, "url": url, "qr_base64": qr_base64(url),
    }]
    actividad.accion = {"texto": "Mostrar QR", "icono": "bi-qr-code", "modal": f"qr-{actividad.id}"}
    actividad.qr_pantalla_completa = con_volver(
        reverse("proyectos:gestionar_registro_equipos", args=[seccion.id]), request,
    )
    actividad.qr_pantalla_texto = "Registro de equipos (abrir, cerrar, descargar el QR)"


def _carpeta_final(seccion_ruta, actividades, grupos, reflexiones):
    """
    Lo que lleva la carpeta de la actividad 22 (Ruta de Jorge 5.5: evidencias,
    planilla de notas y acuerdo firmado), juntado durante toda la Ruta.
    """
    archivos = {a.ruta_actividad.orden: len(a.evidencias.all()) for a in actividades}
    acuerdos = archivos.get(11, 0)
    registradas = sum(1 for momento in MOMENTO_POR_ORDEN.values() if reflexiones.get(momento))

    def fila(texto, detalle, listo):
        return {"texto": texto, "detalle": detalle, "listo": listo}

    def n_archivos(n):
        return f"{n} archivo{'s' if n != 1 else ''}" if n else "Falta"

    return {
        "filas": [
            fila("Instrumento de evaluación (actividad 9)", n_archivos(archivos.get(9, 0)), archivos.get(9, 0) > 0),
            fila(
                "Acuerdos firmados (actividad 11)",
                f"{min(acuerdos, grupos)} de {grupos} grupos" if grupos else n_archivos(acuerdos),
                acuerdos >= grupos if grupos else acuerdos > 0,
            ),
            fila("Reflexiones registradas (12, 15 y 17)", f"{registradas} de 3", registradas == 3),
            fila("Fotos y productos (actividad 16)", n_archivos(archivos.get(16, 0)), archivos.get(16, 0) > 0),
            fila("Planilla de notas (aquí)", n_archivos(archivos.get(22, 0)), archivos.get(22, 0) > 0),
        ],
        "url_zip": reverse("rutas:descargar_mi_carpeta", args=[seccion_ruta.id]),
    }


def preparar_actividades(request, seccion_ruta, actividades):
    """
    Agrega a cada actividad lo que muestra la Ruta paso a paso:
    accion (botón principal), que_hacer, nota_precarga, progreso,
    evidencia_pedida, qrs (popup de las actividades 13 y 19) y los recursos de "¿Cómo se hace?".
    """
    seccion = seccion_ruta.seccion
    cache = {}
    grupos, grupos_con_socio = _equipos(seccion)
    reflexiones = _reflexiones_registradas(seccion)
    socios_elegidos = socios_elegidos_seccion(seccion).count()
    correo_coordinacion = _correo_coordinacion()

    for actividad in actividades:
        ruta_actividad = actividad.ruta_actividad
        orden = ruta_actividad.orden
        actividad.url_recurso = url_recurso(actividad)
        actividad.que_hacer = QUE_HACER.get(orden)
        actividad.nota_precarga = NOTA_PRECARGA.get(orden)
        actividad.evidencia_pedida = EVIDENCIA_PEDIDA.get(orden)
        actividad.progreso = None
        actividad.accion = None
        actividad.qrs = []
        actividad.qr_pantalla_completa = None
        actividad.qr_pantalla_texto = None
        actividad.enlace_formulario = None

        # 13 usa el registro de equipos, no un formulario (aunque una versión
        # de la Ruta lo tenga vinculado).
        version = None if orden == 13 else _version_formulario(ruta_actividad, cache)
        enlace = None
        if version is not None:
            enlace = obtener_o_crear_enlace_seccion(version, seccion, request.user)
        actividad.enlace_formulario = enlace

        if orden == 13:
            # Registrar al socio (Ruta docente.txt: "un estudiante por grupo
            # completa el formulario oficial"): el Registro de equipo pide los
            # datos del Registro de Socios Comunitarios y los guarda en el
            # socio y la participación del equipo, una sola vez.
            _registro_equipos(request, seccion, actividad)
        elif enlace is not None:
            url = reverse("encuestas:responder", args=[enlace.token])
            texto, icono = TEXTO_BOTON.get(orden, ("Llenar formulario", "bi-pencil-square"))
            actividad.accion = {"texto": texto, "icono": icono, "url": url, "nueva_pestana": True}
            if version.plantilla.codigo == precarga.FORMALIZACION_ACUERDOS:
                # Un acuerdo por grupo, precargado con su socio y sus integrantes.
                opciones = _acuerdos_por_grupo(seccion, url)
                if opciones:
                    actividad.accion["opciones"] = opciones
        elif orden == 10:
            actividad.accion = {
                "texto": "Pedir carta", "icono": "bi-envelope-paper",
                "url": reverse("cartas:solicitar_carta_docente", args=[seccion.id]),
            }
            if _carta_estudiantes(request, seccion, actividad):
                actividad.accion["opciones"] = [
                    {"texto": "La pido yo", "url": con_volver(actividad.accion["url"], request), "misma_pestana": True},
                    {"texto": "Mostrar QR para que la pida un estudiante", "modal": f"qr-{actividad.id}"},
                ]
        elif orden == 6:
            # Seleccionar Socios Comunitarios: los que elija son los que verán
            # los estudiantes al registrar su equipo (RF-SC-03, actividad 13).
            actividad.accion = {
                "texto": "Elegir socios", "icono": "bi-building",
                "url": f"{reverse('socios:catalogo_docente')}?seccion={seccion.id}",
            }
        elif orden == 19:
            # Las encuestas de evaluación A+S (estudiantes y docentes) en un popup.
            actividad.qrs = formularios_qr_de_proceso(request, "EVALUACION_AS")
            if actividad.qrs:
                actividad.accion = {"texto": "Mostrar QR de encuestas", "icono": "bi-qr-code", "modal": f"qr-{actividad.id}"}
                actividad.qr_pantalla_completa = (
                    f"{reverse('rutas:formularios_qr')}?proceso=EVALUACION_AS&ruta={seccion_ruta.id}"
                )
        elif orden in (2, 3) and correo_coordinacion:
            texto, asunto = CONTACTO_COORDINACION[orden]
            actividad.accion = {
                "texto": texto, "icono": "bi-envelope",
                "url": _mailto(correo_coordinacion, asunto, seccion), "nueva_pestana": True,
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
        elif orden == 6 and socios_elegidos:
            actividad.progreso = f"{socios_elegidos} socio{'s' if socios_elegidos != 1 else ''} elegido{'s' if socios_elegidos != 1 else ''}"
        elif orden in MOMENTO_POR_ORDEN and reflexiones.get(MOMENTO_POR_ORDEN[orden]):
            actividad.progreso = "Registrada"

        actividad.material = MATERIAL_POR_ORDEN.get(orden, [])
        actividad.carpeta = (
            _carpeta_final(seccion_ruta, actividades, grupos, reflexiones) if orden == 22 else None
        )
        actividad.acuerdos = []
        actividad.acuerdo_en_blanco = None
        if version is not None and version.plantilla.codigo == precarga.FORMALIZACION_ACUERDOS:
            url_acuerdo = reverse("rutas:descargar_acuerdo", args=[actividad.id])
            actividad.acuerdo_en_blanco = url_acuerdo
            actividad.acuerdos = [
                {"texto": acuerdo.nombre_acuerdo(respuesta, numero), "url": f"{url_acuerdo}?respuesta={respuesta.id}"}
                for numero, respuesta in enumerate(acuerdo.acuerdos_de(seccion), start=1)
            ]

        # Lo que se abre en la misma pestaña vuelve a la Ruta con su "Volver".
        if actividad.accion and actividad.accion.get("url") and not actividad.accion.get("nueva_pestana"):
            actividad.accion["url"] = con_volver(actividad.accion["url"], request)

        actividad.dinamicas = [
            {"nombre": nombre, "detalle": DETALLE_DINAMICA.get(nombre, "")}
            for nombre in DINAMICAS.get(MOMENTO_POR_ORDEN.get(orden), [])
        ]
        actividad.ejemplo_evidencia = "Ej.: Grupo 2" if orden == 11 else "Descripción (opcional)"

        # Lo que se ve en "¿Cómo se hace?": la descripción y los recursos.
        actividad.recurso_extra = (
            actividad.url_recurso
            if actividad.url_recurso and orden not in (1, 10, 19)
            else None
        )
        # 13: el docente también puede asignar el socio a un grupo él mismo.
        actividad.recurso_texto = "Asignar yo el socio a un grupo" if orden == 13 else None
        # 6 y 9: la Ruta de Jorge ofrece el apoyo de Coordinación.
        if orden in (6, 9) and correo_coordinacion and not actividad.recurso_extra:
            texto, asunto = CONTACTO_COORDINACION[orden]
            actividad.recurso_extra = _mailto(correo_coordinacion, asunto, seccion)
            actividad.recurso_texto = texto
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


def plantillas_de_la_ruta():
    """
    Ids de los formularios que se usan en la Ruta Docente: los que se llenan
    en una actividad, los vinculados a una actividad y las tres encuestas de
    evaluación A+S (actividad 19). La lista de Formularios los separa de los
    demás.
    """
    from core.indicadores import ENCUESTAS_SATISFACCION
    from encuestas.models import FormularioPlantilla

    from .models import RutaActividad

    codigos = set(FORMULARIO_POR_ORDEN.values()) | {codigo for codigo, _ in ENCUESTAS_SATISFACCION}
    ids = set(FormularioPlantilla.objects.filter(codigo__in=codigos).values_list("id", flat=True))
    ids |= set(
        RutaActividad.objects.exclude(formulario_version=None)
        .values_list("formulario_version__plantilla_id", flat=True)
    )
    return ids
