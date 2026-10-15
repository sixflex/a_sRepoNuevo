import shutil
import zipfile
from decimal import Decimal
from pathlib import Path

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from archivos.services import abrir_archivo
from auditoria.services import registrar_auditoria
from comunicaciones.models import PlantillaCorreo
from comunicaciones.services import EmailService
from encuestas import services as encuestas_services
from encuestas.models import EnlaceFormulario
from socios.models import InvitacionCierre, ParticipacionSocio, SocioComunitario
from socios.services import correo_contacto_principal
from django.db.models import Count, Max, Q

from .models import RutaActividad, RutaVersion, SeccionActividad, SeccionRuta


@transaction.atomic
def asignar_ruta_a_seccion(seccion, ruta_version):
    seccion_ruta, creada = SeccionRuta.objects.get_or_create(
        seccion=seccion,
        defaults={
            "ruta_version": ruta_version,
            "estado": "EN_PROGRESO",
            "porcentaje_final": Decimal("0.00"),
        },
    )

    if not creada and seccion_ruta.ruta_version_id != ruta_version.id:
        raise ValueError(
            "La sección ya tiene asignada una versión diferente de la Ruta A+S."
        )

    actividades = RutaActividad.objects.filter(
        ruta_version=ruta_version
    ).order_by("orden")

    for actividad in actividades:
        SeccionActividad.objects.get_or_create(
            seccion_ruta=seccion_ruta,
            ruta_actividad=actividad,
            defaults={
                "estado": "PENDIENTE",
            },
        )

    return seccion_ruta


def obtener_version_ruta_vigente():
    return (
        RutaVersion.objects
        .filter(
            plantilla__nombre="Ruta del Docente A+S",
            plantilla__activo=True,
            estado="ACTIVA",
        )
        .order_by("-numero_version")
        .first()
    )


def asignar_ruta_as_si_corresponde(seccion):
    es_as = seccion.seccion_carreras.filter(
        declaracion_as=True
    ).exists()

    if not es_as:
        return None

    ruta_existente = SeccionRuta.objects.filter(
        seccion=seccion
    ).first()

    if ruta_existente is not None:
        return asignar_ruta_a_seccion(
            seccion,
            ruta_existente.ruta_version,
        )

    ruta_version = obtener_version_ruta_vigente()

    if ruta_version is None:
        return None

    return asignar_ruta_a_seccion(
        seccion,
        ruta_version,
    )

def con_avance(rutas):
    """
    Anota en cada SeccionRuta sus actividades obligatorias totales y
    completadas (RF-RUT-03: las opcionales no cuentan). Es el mismo cálculo
    del inicio docente; el panel del coordinador lo usa por carrera.
    """
    return rutas.annotate(
        total_obligatorias=Count(
            "actividades",
            filter=Q(actividades__ruta_actividad__es_obligatoria=True),
        ),
        completadas_obligatorias=Count(
            "actividades",
            filter=Q(
                actividades__ruta_actividad__es_obligatoria=True,
                actividades__completada_por_docente__isnull=False,
            ),
        ),
    )


def porcentaje_avance(completadas, total):
    """Porcentaje entero de obligatorias completadas (0 si no hay obligatorias)."""
    return round(completadas * 100 / total) if total else 0


def url_recurso(seccion_actividad):
    """
    URL de la acción asociada a la actividad (recurso_url). Admite {seccion}
    y {actividad} para acciones que dependen de la sección, como solicitar
    la carta o registrar al Socio Comunitario.
    """
    url = seccion_actividad.ruta_actividad.recurso_url

    if not url:
        return None

    return (
        url
        .replace("{seccion}", str(seccion_actividad.seccion_ruta.seccion_id))
        .replace("{actividad}", str(seccion_actividad.id))
    )


def enlaces_abiertos_por_plantilla(plantilla_ids):
    """
    Primer enlace general abierto de cada plantilla. Se busca por plantilla
    y no por versión porque al publicar una versión nueva el enlace pasa a ella.
    """
    enlaces = (
        EnlaceFormulario.objects
        .filter(
            version__plantilla_id__in=plantilla_ids,
            activo=True,
            seccion__isnull=True,
        )
        .select_related("version__plantilla")
        .order_by("id")
    )

    resultado = {}

    for enlace in enlaces:
        plantilla_id = enlace.version.plantilla_id

        if (
            plantilla_id not in resultado
            and encuestas_services.enlace_abierto(enlace)
        ):
            resultado[plantilla_id] = enlace

    return resultado


# ---------------------------------------------------------------------------
# Actividad de cierre e invitación al Socio Comunitario (RF-EVI-04 a RF-EVI-06)
# ---------------------------------------------------------------------------

# La actividad de cierre se reconoce por su configuración de recordatorio
# (RF-RUT-04), no por su número de orden.
RECORDATORIO_INVITACION_CIERRE = "invitacion_cierre"
OBSERVACION_SIN_CIERRE = "No habrá actividad de cierre."

MODO_PLATAFORMA = "PLATAFORMA"
MODO_EXTERNO = "EXTERNO"

# Valores del modelo de BD: ASISTIRA / NO / SIN_RESPUESTA
ASISTIRA = "ASISTIRA"
NO_ASISTIRA = "NO"
SIN_RESPUESTA = "SIN_RESPUESTA"

ETIQUETAS_RESPUESTA = {
    ASISTIRA: "Asistirá",
    NO_ASISTIRA: "No asistirá",
    SIN_RESPUESTA: "Sin respuesta",
}

PLANTILLA_INVITACION_CIERRE = "INVITACION_CIERRE"

ASUNTO_INVITACION_CIERRE = (
    "Invitación a la actividad de cierre A+S · {{ asignatura }}"
)

CUERPO_INVITACION_CIERRE = """Estimado/a {{ socio }}:

{{ docente }} le invita a la actividad de cierre del proyecto de Aprendizaje + Servicio de la asignatura {{ asignatura }} (sección {{ seccion }}, {{ campus }}), donde los estudiantes presentarán sus informes y trabajos finales.

Por favor confirme su asistencia:

Asistiré: {{ url_asistire }}
No asistiré: {{ url_no_asistire }}

Coordinación A+S
Universidad Autónoma de Chile
"""


def es_actividad_cierre(ruta_actividad):
    config = ruta_actividad.config_recordatorio_json or {}
    return config.get("recordatorio") == RECORDATORIO_INVITACION_CIERRE


def socios_de_seccion(seccion):
    """Socios con una participación vigente en la sección o en sus equipos."""
    participaciones = ParticipacionSocio.objects.filter(
        Q(equipo__seccion=seccion) | Q(seccion=seccion),
        fecha_fin__isnull=True,
    )

    return (
        SocioComunitario.objects
        .filter(participaciones__in=participaciones)
        .distinct()
        .order_by("nombre_organizacion")
    )


def indicar_sin_cierre(seccion_actividad, docente, request):
    """
    El Docente indica que no habrá actividad de cierre. No genera
    incumplimiento (RF-EVI-04): la actividad queda completada con esa
    observación.
    """
    seccion_actividad.completada_por_docente = docente
    seccion_actividad.estado = "COMPLETADA"
    seccion_actividad.fecha_completada = timezone.now()
    seccion_actividad.observacion = OBSERVACION_SIN_CIERRE
    seccion_actividad.save(
        update_fields=[
            "completada_por_docente",
            "estado",
            "fecha_completada",
            "observacion",
        ]
    )

    registrar_auditoria(
        request=request,
        entidad="SeccionActividad",
        entidad_id=seccion_actividad.pk,
        accion="SIN_ACTIVIDAD_CIERRE",
        valores_nuevos={"observacion": OBSERVACION_SIN_CIERRE},
    )


@transaction.atomic
def crear_invitaciones_cierre(seccion_ruta, socios, modo, request):
    invitaciones = []

    for socio in socios:
        invitacion, creada = InvitacionCierre.objects.get_or_create(
            seccion_ruta=seccion_ruta,
            socio=socio,
            defaults={
                "modo_contacto": modo,
                "respuesta": SIN_RESPUESTA,
            },
        )

        if creada:
            registrar_auditoria(
                request=request,
                entidad="InvitacionCierre",
                entidad_id=invitacion.pk,
                accion="CREAR_INVITACION_CIERRE",
                valores_nuevos={
                    "socio_id": socio.pk,
                    "modo_contacto": modo,
                },
            )

            invitaciones.append(invitacion)

    return invitaciones


def _plantilla_invitacion_cierre():
    PlantillaCorreo.objects.get_or_create(
        codigo=PLANTILLA_INVITACION_CIERRE,
        defaults={
            "asunto_template": ASUNTO_INVITACION_CIERRE,
            "cuerpo_template": CUERPO_INVITACION_CIERRE,
            "activo": True,
        },
    )


def enviar_invitacion_cierre(invitacion, request):
    """
    Envía el correo con los enlaces únicos Asistiré / No asistiré (RF-EVI-05).
    Devuelve el EnvioCorreo, o None si el socio no tiene correo de contacto.
    """
    correo = correo_contacto_principal(invitacion.socio)

    if not correo:
        return None

    _plantilla_invitacion_cierre()

    seccion = invitacion.seccion_ruta.seccion
    docente = getattr(request.user, "perfil_docente", None)

    def enlace(respuesta):
        return request.build_absolute_uri(
            reverse(
                "rutas:responder_invitacion_cierre",
                args=[invitacion.token, respuesta],
            )
        )

    envio = EmailService.enviar_correo(
        PLANTILLA_INVITACION_CIERRE,
        correo,
        {
            "socio": invitacion.socio.nombre_organizacion,
            "docente": (
                f"El/la docente {docente.nombres} {docente.apellidos}"
                if docente
                else "El equipo docente"
            ),
            "asignatura": seccion.asignatura.nombre,
            "seccion": seccion.seccion,
            "campus": seccion.campus,
            "url_asistire": enlace("asistire"),
            "url_no_asistire": enlace("no-asistire"),
        },
        invitacion_cierre=invitacion,
    )

    if envio.resultado == "OK":
        invitacion.fecha_envio = envio.fecha_envio
        invitacion.save(update_fields=["fecha_envio"])

    return envio


def registrar_respuesta_cierre(invitacion, respuesta, request, actor_externo=None):
    """Registra Asistirá / No asistirá / Sin respuesta (RF-EVI-06); no bloquea la Ruta."""
    anterior = invitacion.respuesta

    invitacion.respuesta = respuesta
    invitacion.fecha_respuesta = (
        None if respuesta == SIN_RESPUESTA else timezone.now()
    )
    invitacion.save(update_fields=["respuesta", "fecha_respuesta"])

    registrar_auditoria(
        request=request,
        entidad="InvitacionCierre",
        entidad_id=invitacion.pk,
        accion="RESPUESTA_INVITACION_CIERRE",
        valores_anteriores={"respuesta": anterior},
        valores_nuevos={"respuesta": respuesta},
        actor_externo=actor_externo,
    )


def recordatorios_cierre(seccion_ruta):
    """
    Acciones pendientes de la invitación al Socio (RF-RUT-04): invitaciones
    por plataforma que no se pudieron enviar y contactos externos sin
    resultado registrado.
    """
    recordatorios = []

    for invitacion in seccion_ruta.invitaciones_cierre.all():
        nombre = invitacion.socio.nombre_organizacion

        if invitacion.modo_contacto == MODO_PLATAFORMA and invitacion.fecha_envio is None:
            recordatorios.append(f"Enviar la invitación al cierre a {nombre}")
        elif invitacion.modo_contacto == MODO_EXTERNO and invitacion.respuesta == SIN_RESPUESTA:
            recordatorios.append(f"Registrar si {nombre} asistirá al cierre")

    return recordatorios


# ---------------------------------------------------------------------------
# Expediente de evidencias en ZIP para acreditación (RF-EVI-03)
# ---------------------------------------------------------------------------

def nombre_zip_expediente(seccion):
    """
    campus_sede_año_período_carrera_asignatura_sección_docente.zip
    (RF-EVI-03 CA1). Varias carreras o docentes se unen con "-".
    """
    partes = [
        seccion.campus.nombre,
        seccion.campus.sede.nombre,
        str(seccion.periodo.anio),
        seccion.periodo.nombre,
        "-".join(seccion.carreras.order_by("nombre").values_list("nombre", flat=True)),
        seccion.asignatura.nombre,
        f"seccion {seccion.seccion}",
        "-".join(
            f"{docente.nombres} {docente.apellidos}"
            for docente in seccion.docentes.order_by("apellidos", "nombres")
        ),
    ]

    return "_".join(slugify(parte) for parte in partes if parte) + ".zip"


def generar_zip_expediente(expediente, destino):
    """
    Escribe en destino un ZIP con las evidencias del expediente, una carpeta
    por actividad. Solo incluye archivos de este expediente. Devuelve los
    nombres de los archivos que no estaban en el almacenamiento.
    """
    evidencias = (
        expediente.evidencias
        .select_related("archivo", "seccion_actividad__ruta_actividad")
        .order_by("seccion_actividad__ruta_actividad__orden", "id")
    )

    usados = set()
    faltantes = []

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zip_expediente:
        for evidencia in evidencias:
            actividad = evidencia.seccion_actividad.ruta_actividad
            carpeta = f"{actividad.orden:02d} - {actividad.nombre}".replace("/", "-")
            nombre = Path(evidencia.archivo.nombre_original).name
            ruta = f"{carpeta}/{nombre}"

            # Dos archivos con el mismo nombre en una actividad no se pisan.
            contador = 2
            while ruta in usados:
                ruta = f"{carpeta}/{Path(nombre).stem} ({contador}){Path(nombre).suffix}"
                contador += 1

            usados.add(ruta)

            try:
                with abrir_archivo(evidencia.archivo) as contenido:
                    with zip_expediente.open(ruta, "w") as salida:
                        shutil.copyfileobj(contenido, salida)
            except FileNotFoundError:
                faltantes.append(nombre)

    return faltantes


def url_recurso(seccion_actividad):
    """
    URL de la acción asociada a la actividad (recurso_url). Admite {seccion}
    y {actividad} para acciones que dependen de la sección, como solicitar
    la carta o registrar al Socio Comunitario.
    """
    url = seccion_actividad.ruta_actividad.recurso_url

    if not url:
        return None

    return (
        url
        .replace("{seccion}", str(seccion_actividad.seccion_ruta.seccion_id))
        .replace("{actividad}", str(seccion_actividad.id))
    )


def enlaces_abiertos_por_plantilla(plantilla_ids):
    """
    Primer enlace general abierto de cada plantilla. Se busca por plantilla
    y no por versión porque al publicar una versión nueva el enlace pasa a ella.
    """
    enlaces = (
        EnlaceFormulario.objects
        .filter(
            version__plantilla_id__in=plantilla_ids,
            activo=True,
            seccion__isnull=True,
        )
        .select_related("version__plantilla")
        .order_by("id")
    )

    resultado = {}

    for enlace in enlaces:
        plantilla_id = enlace.version.plantilla_id

        if (
            plantilla_id not in resultado
            and encuestas_services.enlace_abierto(enlace)
        ):
            resultado[plantilla_id] = enlace

    return resultado


# ---------------------------------------------------------------------------
# Actividad de cierre e invitación al Socio Comunitario (RF-EVI-04 a RF-EVI-06)
# ---------------------------------------------------------------------------

# La actividad de cierre se reconoce por su configuración de recordatorio
# (RF-RUT-04), no por su número de orden.
RECORDATORIO_INVITACION_CIERRE = "invitacion_cierre"
OBSERVACION_SIN_CIERRE = "No habrá actividad de cierre."

MODO_PLATAFORMA = "PLATAFORMA"
MODO_EXTERNO = "EXTERNO"

# Valores del modelo de BD: ASISTIRA / NO / SIN_RESPUESTA
ASISTIRA = "ASISTIRA"
NO_ASISTIRA = "NO"
SIN_RESPUESTA = "SIN_RESPUESTA"

ETIQUETAS_RESPUESTA = {
    ASISTIRA: "Asistirá",
    NO_ASISTIRA: "No asistirá",
    SIN_RESPUESTA: "Sin respuesta",
}

PLANTILLA_INVITACION_CIERRE = "INVITACION_CIERRE"

ASUNTO_INVITACION_CIERRE = (
    "Invitación a la actividad de cierre A+S · {{ asignatura }}"
)

CUERPO_INVITACION_CIERRE = """Estimado/a {{ socio }}:

{{ docente }} le invita a la actividad de cierre del proyecto de Aprendizaje + Servicio de la asignatura {{ asignatura }} (sección {{ seccion }}, {{ campus }}), donde los estudiantes presentarán sus informes y trabajos finales.

Por favor confirme su asistencia:

Asistiré: {{ url_asistire }}
No asistiré: {{ url_no_asistire }}

Coordinación A+S
Universidad Autónoma de Chile
"""


def es_actividad_cierre(ruta_actividad):
    config = ruta_actividad.config_recordatorio_json or {}
    return config.get("recordatorio") == RECORDATORIO_INVITACION_CIERRE


def socios_de_seccion(seccion):
    """Socios con una participación vigente en la sección o en sus equipos."""
    participaciones = ParticipacionSocio.objects.filter(
        Q(equipo__seccion=seccion) | Q(seccion=seccion),
        fecha_fin__isnull=True,
    )

    return (
        SocioComunitario.objects
        .filter(participaciones__in=participaciones)
        .distinct()
        .order_by("nombre_organizacion")
    )


def indicar_sin_cierre(seccion_actividad, docente, request):
    """
    El Docente indica que no habrá actividad de cierre. No genera
    incumplimiento (RF-EVI-04): la actividad queda completada con esa
    observación.
    """
    seccion_actividad.completada_por_docente = docente
    seccion_actividad.estado = "COMPLETADA"
    seccion_actividad.fecha_completada = timezone.now()
    seccion_actividad.observacion = OBSERVACION_SIN_CIERRE
    seccion_actividad.save(
        update_fields=[
            "completada_por_docente",
            "estado",
            "fecha_completada",
            "observacion",
        ]
    )

    registrar_auditoria(
        request=request,
        entidad="SeccionActividad",
        entidad_id=seccion_actividad.pk,
        accion="SIN_ACTIVIDAD_CIERRE",
        valores_nuevos={"observacion": OBSERVACION_SIN_CIERRE},
    )


@transaction.atomic
def crear_invitaciones_cierre(seccion_ruta, socios, modo, request):
    invitaciones = []

    for socio in socios:
        invitacion, creada = InvitacionCierre.objects.get_or_create(
            seccion_ruta=seccion_ruta,
            socio=socio,
            defaults={
                "modo_contacto": modo,
                "respuesta": SIN_RESPUESTA,
            },
        )

        if creada:
            registrar_auditoria(
                request=request,
                entidad="InvitacionCierre",
                entidad_id=invitacion.pk,
                accion="CREAR_INVITACION_CIERRE",
                valores_nuevos={
                    "socio_id": socio.pk,
                    "modo_contacto": modo,
                },
            )

            invitaciones.append(invitacion)

    return invitaciones


def _plantilla_invitacion_cierre():
    PlantillaCorreo.objects.get_or_create(
        codigo=PLANTILLA_INVITACION_CIERRE,
        defaults={
            "asunto_template": ASUNTO_INVITACION_CIERRE,
            "cuerpo_template": CUERPO_INVITACION_CIERRE,
            "activo": True,
        },
    )


def enviar_invitacion_cierre(invitacion, request):
    """
    Envía el correo con los enlaces únicos Asistiré / No asistiré (RF-EVI-05).
    Devuelve el EnvioCorreo, o None si el socio no tiene correo de contacto.
    """
    correo = correo_contacto_principal(invitacion.socio)

    if not correo:
        return None

    _plantilla_invitacion_cierre()

    seccion = invitacion.seccion_ruta.seccion
    docente = getattr(request.user, "perfil_docente", None)

    def enlace(respuesta):
        return request.build_absolute_uri(
            reverse(
                "rutas:responder_invitacion_cierre",
                args=[invitacion.token, respuesta],
            )
        )

    envio = EmailService.enviar_correo(
        PLANTILLA_INVITACION_CIERRE,
        correo,
        {
            "socio": invitacion.socio.nombre_organizacion,
            "docente": (
                f"El/la docente {docente.nombres} {docente.apellidos}"
                if docente
                else "El equipo docente"
            ),
            "asignatura": seccion.asignatura.nombre,
            "seccion": seccion.seccion,
            "campus": seccion.campus,
            "url_asistire": enlace("asistire"),
            "url_no_asistire": enlace("no-asistire"),
        },
        invitacion_cierre=invitacion,
    )

    if envio.resultado == "OK":
        invitacion.fecha_envio = envio.fecha_envio
        invitacion.save(update_fields=["fecha_envio"])

    return envio


def registrar_respuesta_cierre(invitacion, respuesta, request, actor_externo=None):
    """Registra Asistirá / No asistirá / Sin respuesta (RF-EVI-06); no bloquea la Ruta."""
    anterior = invitacion.respuesta

    invitacion.respuesta = respuesta
    invitacion.fecha_respuesta = (
        None if respuesta == SIN_RESPUESTA else timezone.now()
    )
    invitacion.save(update_fields=["respuesta", "fecha_respuesta"])

    registrar_auditoria(
        request=request,
        entidad="InvitacionCierre",
        entidad_id=invitacion.pk,
        accion="RESPUESTA_INVITACION_CIERRE",
        valores_anteriores={"respuesta": anterior},
        valores_nuevos={"respuesta": respuesta},
        actor_externo=actor_externo,
    )


def recordatorios_cierre(seccion_ruta):
    """
    Acciones pendientes de la invitación al Socio (RF-RUT-04): invitaciones
    por plataforma que no se pudieron enviar y contactos externos sin
    resultado registrado.
    """
    recordatorios = []

    for invitacion in seccion_ruta.invitaciones_cierre.all():
        nombre = invitacion.socio.nombre_organizacion

        if invitacion.modo_contacto == MODO_PLATAFORMA and invitacion.fecha_envio is None:
            recordatorios.append(f"Enviar la invitación al cierre a {nombre}")
        elif invitacion.modo_contacto == MODO_EXTERNO and invitacion.respuesta == SIN_RESPUESTA:
            recordatorios.append(f"Registrar si {nombre} asistirá al cierre")

    return recordatorios


# ---------------------------------------------------------------------------
# Expediente de evidencias en ZIP para acreditación (RF-EVI-03)
# ---------------------------------------------------------------------------

def nombre_zip_expediente(seccion):
    """
    campus_sede_año_período_carrera_asignatura_sección_docente.zip
    (RF-EVI-03 CA1). Varias carreras o docentes se unen con "-".
    """
    partes = [
        seccion.campus.nombre,
        seccion.campus.sede.nombre,
        str(seccion.periodo.anio),
        seccion.periodo.nombre,
        "-".join(seccion.carreras.order_by("nombre").values_list("nombre", flat=True)),
        seccion.asignatura.nombre,
        f"seccion {seccion.seccion}",
        "-".join(
            f"{docente.nombres} {docente.apellidos}"
            for docente in seccion.docentes.order_by("apellidos", "nombres")
        ),
    ]

    return "_".join(slugify(parte) for parte in partes if parte) + ".zip"


def generar_zip_expediente(expediente, destino):
    """
    Escribe en destino un ZIP con las evidencias del expediente, una carpeta
    por actividad. Solo incluye archivos de este expediente. Devuelve los
    nombres de los archivos que no estaban en el almacenamiento.
    """
    evidencias = (
        expediente.evidencias
        .select_related("archivo", "seccion_actividad__ruta_actividad")
        .order_by("seccion_actividad__ruta_actividad__orden", "id")
    )

    usados = set()
    faltantes = []

    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zip_expediente:
        for evidencia in evidencias:
            actividad = evidencia.seccion_actividad.ruta_actividad
            carpeta = f"{actividad.orden:02d} - {actividad.nombre}".replace("/", "-")
            nombre = Path(evidencia.archivo.nombre_original).name
            ruta = f"{carpeta}/{nombre}"

            # Dos archivos con el mismo nombre en una actividad no se pisan.
            contador = 2
            while ruta in usados:
                ruta = f"{carpeta}/{Path(nombre).stem} ({contador}){Path(nombre).suffix}"
                contador += 1

            usados.add(ruta)

            try:
                with abrir_archivo(evidencia.archivo) as contenido:
                    with zip_expediente.open(ruta, "w") as salida:
                        shutil.copyfileobj(contenido, salida)
            except FileNotFoundError:
                faltantes.append(nombre)

    return faltantes

@transaction.atomic
def crear_nueva_version_ruta(ruta_version_origen, usuario=None):
    ruta_version_origen = RutaVersion.objects.select_for_update().get(
        pk=ruta_version_origen.pk
    )

    ultima_version = (
        RutaVersion.objects.filter(
            plantilla=ruta_version_origen.plantilla
        )
        .aggregate(max_version=Max("numero_version"))["max_version"]
    )

    nueva_version = RutaVersion.objects.create(
        plantilla=ruta_version_origen.plantilla,
        creado_por_usuario=usuario,
        numero_version=(ultima_version or 0) + 1,
        estado="BORRADOR",
        fecha_vigencia_desde=None,
        fecha_vigencia_hasta=None,
    )

    actividades_originales = RutaActividad.objects.filter(
        ruta_version=ruta_version_origen
    ).order_by("orden", "pk")

    nuevas_actividades = [
        RutaActividad(
            ruta_version=nueva_version,
            formulario_version=actividad.formulario_version,
            archivo_recurso=actividad.archivo_recurso,
            etapa=actividad.etapa,
            nombre=actividad.nombre,
            descripcion=actividad.descripcion,
            es_obligatoria=actividad.es_obligatoria,
            orden=actividad.orden,
            recurso_url=actividad.recurso_url,
            config_recordatorio_json=actividad.config_recordatorio_json,
        )
        for actividad in actividades_originales
    ]

    RutaActividad.objects.bulk_create(nuevas_actividades)

    return nueva_version