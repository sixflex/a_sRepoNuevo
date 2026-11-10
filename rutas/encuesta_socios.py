"""
Encuesta de satisfacción a los Socios Comunitarios, enviada por el
Coordinador una vez al final del período (reunión con el cliente 10-11-2026).

Antes cada docente debía pedirla en la actividad 19 de la Ruta; ahora el
Coordinador la envía a todos los socios del período desde un solo botón.
Cada socio recibe su propio enlace (EnlaceFormulario.socio), así su
respuesta queda asociada a él y se sabe quién ya respondió. No se agregan
tablas: el enlace marca a quién se le envió y EnvioCorreo guarda el envío.
"""

from django.db.models import Q
from django.urls import reverse

from comunicaciones.models import PlantillaCorreo
from comunicaciones.services import EmailService
from encuestas import services as encuestas_services
from encuestas.models import EnlaceFormulario, FormularioVersion, RespuestaFormulario
from socios.models import ParticipacionSocio, SocioComunitario
from socios.services import correo_contacto_principal

CODIGO_ENCUESTA = "EVALUACION_AS_SOCIOS"
PLANTILLA = "ENCUESTA_SATISFACCION_SOCIO"

ASUNTO = "Encuesta de satisfacción A+S · {{ periodo }}"
CUERPO = """{% autoescape off %}Estimado/a {{ socio }}:

Gracias por trabajar con nuestros estudiantes de Aprendizaje + Servicio durante {{ periodo }}.

Nos ayudaría mucho conocer su opinión. La encuesta toma unos 5 minutos:

{{ url }}

Coordinación Aprendizaje + Servicio
Universidad Autónoma de Chile{% endautoescape %}"""


def version_encuesta():
    return (
        FormularioVersion.objects
        .filter(plantilla__codigo=CODIGO_ENCUESTA, plantilla__activo=True, estado="PUBLICADA")
        .select_related("plantilla")
        .order_by("-numero_version", "-pk")
        .first()
    )


def socios_del_periodo(periodo):
    """Socios que trabajaron con alguna sección del período."""
    participaciones = ParticipacionSocio.objects.filter(
        Q(periodo=periodo) | Q(equipo__seccion__periodo=periodo) | Q(seccion__periodo=periodo)
    )
    return (
        SocioComunitario.objects
        .filter(participaciones__in=participaciones)
        .distinct()
        .order_by("nombre_organizacion")
    )


def _ventana(periodo):
    """
    Desde cuándo y hasta cuándo un enlace cuenta para el período: desde su
    inicio (o el 1 de enero de su año) hasta que empieza el período siguiente.
    El enlace no guarda el período, así que se ubica por su fecha.
    """
    from datetime import date, datetime, time

    from academico.models import PeriodoAcademico
    from django.utils import timezone

    def momento(dia):
        return timezone.make_aware(datetime.combine(dia, time.min))

    desde = periodo.fecha_inicio or date(periodo.anio, 1, 1)
    siguiente = (
        PeriodoAcademico.objects
        .filter(fecha_inicio__gt=desde)
        .exclude(pk=periodo.pk)
        .order_by("fecha_inicio")
        .values_list("fecha_inicio", flat=True)
        .first()
    )
    return momento(desde), (momento(siguiente) if siguiente else None)


def _enlaces_del_periodo(version, periodo):
    desde, hasta = _ventana(periodo)
    enlaces = EnlaceFormulario.objects.filter(
        version__plantilla=version.plantilla, socio__isnull=False, fecha_inicio__gte=desde,
    )
    if hasta:
        enlaces = enlaces.filter(fecha_inicio__lt=hasta)
    return enlaces.order_by("-id")


def estado_envio(periodo):
    """
    Lista de socios del período con su correo y si ya se les envió o
    respondieron. Devuelve (version, filas).
    """
    version = version_encuesta()
    filas = []
    respondieron = set()
    enlaces = {}
    if version is not None:
        for enlace in _enlaces_del_periodo(version, periodo):
            enlaces.setdefault(enlace.socio_id, enlace)
        respondieron = set(
            RespuestaFormulario.objects
            .filter(enlace__in=list(enlaces.values()))
            .values_list("socio_id", flat=True)
        )
    for socio in socios_del_periodo(periodo):
        enlace = enlaces.get(socio.id)
        filas.append({
            "socio": socio,
            "correo": correo_contacto_principal(socio),
            "enviado": enlace is not None,
            "respondio": socio.id in respondieron,
            "enlace": enlace,
        })
    return version, filas


def _plantilla():
    PlantillaCorreo.objects.get_or_create(
        codigo=PLANTILLA,
        defaults={"asunto_template": ASUNTO, "cuerpo_template": CUERPO, "activo": True},
    )


def enviar(periodo, request, reenviar=False):
    """
    Envía la encuesta a los socios del período con correo. Sin reenviar,
    solo a quienes aún no se les envió. Devuelve un resumen con los conteos.
    """
    version, filas = estado_envio(periodo)
    resumen = {"enviados": 0, "errores": [], "sin_correo": [], "omitidos": 0}
    if version is None:
        return None
    _plantilla()

    for fila in filas:
        socio = fila["socio"]
        if fila["respondio"] or (fila["enviado"] and not reenviar):
            resumen["omitidos"] += 1
            continue
        if not fila["correo"]:
            resumen["sin_correo"].append(socio.nombre_organizacion)
            continue

        enlace = fila["enlace"]
        nuevo = enlace is None or not encuestas_services.enlace_abierto(enlace)
        if nuevo:
            enlace = encuestas_services.crear_enlace(
                version, usuario=request.user, socio=socio,
            )
        url = request.build_absolute_uri(reverse("encuestas:responder", args=[enlace.token]))
        envio = EmailService.enviar_correo(
            PLANTILLA, fila["correo"],
            {"socio": socio.nombre_organizacion, "periodo": periodo.nombre, "url": url},
        )
        if envio.resultado == "OK":
            resumen["enviados"] += 1
        else:
            if nuevo:
                # Si el correo no salió, el socio sigue como "por enviar".
                enlace.delete()
            resumen["errores"].append(socio.nombre_organizacion)
    return resumen
