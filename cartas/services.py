import hashlib
import logging
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone

from archivos.services import guardar_archivo
from auditoria.services import registrar_auditoria
from comunicaciones.services import EmailService

from .models import CartaDocumento, SolicitudCarta
from .plantilla_oficial import construir_pdf, recursos_carta


MAX_ALUMNOS_POR_CARTA = 6
MESES_ANTIGUEDAD_ALERTA = 12
CODIGO_PLANTILLA_CARTA = "CARTA_PRESENTACION_DOCENTE"

logger = logging.getLogger(__name__)


def verificar_alerta_antiguedad_socio(socio):

    if not socio:
        return False

    hace_un_ano = timezone.now().date() - timedelta(days=365)
    ultima_participacion = socio.participaciones.trabajadas().order_by("-fecha_inicio").first()

    if not ultima_participacion or not ultima_participacion.fecha_inicio:
        return True

    return ultima_participacion.fecha_inicio < hace_un_ano


def generar_pdf_carta(solicitud, usuario, estudiantes=None):
    if solicitud.estado not in {"BORRADOR", "APROBADA"}:
        raise ValueError(
            "La solicitud debe estar en borrador o aprobada."
        )

    if estudiantes is None:
        estudiantes = list(
            solicitud.estudiantes.order_by("orden")
        )

    if not estudiantes:
        raise ValueError(
            "La solicitud no tiene estudiantes asociados."
        )

    if len(estudiantes) > MAX_ALUMNOS_POR_CARTA:
        raise ValueError(
            f"Una carta de presentación no puede contener más de {MAX_ALUMNOS_POR_CARTA} estudiantes."
        )

    docente = solicitud.docente_derivador
    nombre_docente = (
        f"{docente.nombres} {docente.apellidos}"
    ).strip() if docente else ""

    # Formato oficial de Coordinación A+S (cartas/plantilla_oficial.py).
    recursos = recursos_carta()
    pdf_bytes = construir_pdf(
        fecha=solicitud.fecha_aprobacion or timezone.now(),
        persona_receptora=solicitud.persona_receptora,
        institucion_receptora=solicitud.institucion_receptora,
        asignatura=solicitud.seccion.asignatura.nombre,
        docente=nombre_docente,
        estudiantes=[(estudiante.nombre, estudiante.rut) for estudiante in estudiantes],
        borrador=solicitud.estado == "BORRADOR",
        recursos=recursos,
    )

    hash_documento = hashlib.sha256(
        pdf_bytes
    ).hexdigest()

    ultima_version = (
        solicitud.documentos
        .order_by("-numero_version")
        .values_list(
            "numero_version",
            flat=True,
        )
        .first()
        or 0
    )

    numero_version = ultima_version + 1

    nombre_archivo = (
        f"carta_presentacion_"
        f"{solicitud.id}_v{numero_version}.pdf"
    )

    archivo_subido = SimpleUploadedFile(
        nombre_archivo,
        pdf_bytes,
        content_type="application/pdf",
    )

    with transaction.atomic():
        archivo = guardar_archivo(
            archivo_subido,
            autor=usuario,
        )

        carta_documento = CartaDocumento.objects.create(
            solicitud=solicitud,
            archivo=archivo,
            generado_por_usuario=usuario,
            numero_version=numero_version,
            tipo="BORRADOR" if solicitud.estado == "BORRADOR" else "PDF",
            fecha_generacion=timezone.now(),
            hash_documento=hash_documento,
            plantilla=recursos["plantilla"],
        )

    return carta_documento


def generar_cartas_agrupadas(solicitud, usuario):

    if solicitud.estado not in {"BORRADOR", "APROBADA"}:
        raise ValueError(
            "La solicitud debe estar en borrador o aprobada."
        )

    todos_estudiantes = list(solicitud.estudiantes.order_by("orden"))

    if not todos_estudiantes:
        raise ValueError("La solicitud no tiene estudiantes asociados.")

    if len(todos_estudiantes) > MAX_ALUMNOS_POR_CARTA:
        raise ValueError(
            f"Una solicitud no puede contener más de "
            f"{MAX_ALUMNOS_POR_CARTA} estudiantes. "
            "Para un grupo mayor, se debe crear otra solicitud."
        )

    carta_doc = generar_pdf_carta(
        solicitud,
        usuario,
        estudiantes=todos_estudiantes,
    )

    return {
        "cartas": [carta_doc],
        "total_cartas": 1,
    }


CAMPO_EDITABLES_COORDINACION = (
    "institucion_receptora",
    "persona_receptora",
    "cargo_receptor",
    "consideraciones",
)


def generar_borrador_carta(solicitud_id, usuario, request=None):
    """SP6-T04 (RF-CAR-04): genera la vista previa marcada como borrador.

    No modifica campus, sede, fecha_solicitud ni el identificador de la
    solicitud: solo cambia el estado a BORRADOR y registra la auditoría.
    """
    with transaction.atomic():
        solicitud = SolicitudCarta.objects.select_for_update().get(pk=solicitud_id)

        if solicitud.estado not in {"PENDIENTE", "BORRADOR"}:
            raise ValueError(
                "Solo se puede generar la vista previa de una solicitud "
                "pendiente o en borrador."
            )

        estado_anterior = solicitud.estado

        if solicitud.estado != "BORRADOR":
            solicitud.estado = "BORRADOR"
            solicitud.save(update_fields=["estado"])

        documento = generar_pdf_carta(solicitud, usuario)

    registrar_auditoria(
        request=request,
        entidad="SolicitudCarta",
        entidad_id=solicitud.id,
        accion="BORRADOR_GENERADO",
        valores_anteriores={"estado": estado_anterior},
        valores_nuevos={
            "estado": solicitud.estado,
            "documento_id": documento.id,
            "numero_version": documento.numero_version,
        },
    )

    return solicitud, documento


def corregir_solicitud_coordinacion(
    solicitud_id,
    datos,
    usuario,
    request=None,
):
    """SP6-T04 (RF-CAR-04): Coordinación corrige datos y regenera el borrador.

    Solo se actualizan los campos editables. El identificador, campus, sede y
    fecha_solicitud quedan intactos (no se incluyen en ``update_fields``).
    """
    with transaction.atomic():
        solicitud = SolicitudCarta.objects.select_for_update().get(pk=solicitud_id)

        if solicitud.estado not in {"PENDIENTE", "BORRADOR"}:
            raise ValueError(
                "Solo se pueden corregir solicitudes pendientes o en borrador."
            )

        valores_anteriores = {
            campo: getattr(solicitud, campo)
            for campo in CAMPO_EDITABLES_COORDINACION
        }
        valores_nuevos = {}

        for campo in CAMPO_EDITABLES_COORDINACION:
            if campo not in datos:
                continue

            valor = datos[campo]
            valores_nuevos[campo] = valor
            setattr(solicitud, campo, valor)

        solicitud.estado = "BORRADOR"
        solicitud.save(
            update_fields=[*CAMPO_EDITABLES_COORDINACION, "estado"]
        )

        documento = generar_pdf_carta(solicitud, usuario)

    registrar_auditoria(
        request=request,
        entidad="SolicitudCarta",
        entidad_id=solicitud.id,
        accion="CORRECCION_BORRADOR",
        valores_anteriores=valores_anteriores,
        valores_nuevos={
            **valores_nuevos,
            "estado": solicitud.estado,
            "documento_id": documento.id,
            "numero_version": documento.numero_version,
        },
    )

    return solicitud, documento


def aprobar_y_enviar_carta(solicitud_id, usuario):
    """RF-CAR-07: al aprobar se genera la carta final y se envía al Docente."""
    with transaction.atomic():
        solicitud = SolicitudCarta.objects.select_for_update().get(pk=solicitud_id)

        if solicitud.estado not in {"PENDIENTE", "BORRADOR"}:
            raise ValueError(
                "Solo se pueden aprobar solicitudes pendientes o en borrador."
            )

        solicitud.estado = "APROBADA"
        solicitud.fecha_aprobacion = timezone.now()
        solicitud.motivo_observacion = None
        solicitud.save(
            update_fields=[
                "estado",
                "fecha_aprobacion",
                "motivo_observacion",
            ]
        )

        cartas = generar_cartas_agrupadas(solicitud, usuario)["cartas"]

    # Si el envío falla la solicitud sigue aprobada y queda pendiente de envío (RF-CAR-08).
    envios = [enviar_carta_docente(carta) for carta in cartas]
    return solicitud, envios


def ultimo_envio(documento):
    return documento.envios_correo.order_by("-id").first()


def enviar_carta_docente(documento):
    """
    Envía la carta al correo institucional del Docente (RN-06).
    Sirve también para reintentar: reutiliza el mismo PDF y no vuelve a enviar si ya salió.
    """
    envio = ultimo_envio(documento)

    if envio and envio.resultado == "OK":
        return envio

    if envio and envio.plantilla_id:
        return EmailService.reintentar_envio(envio.id)

    solicitud = documento.solicitud
    docente = solicitud.docente_derivador

    return EmailService.enviar_correo(
        codigo_plantilla=CODIGO_PLANTILLA_CARTA,
        destinatario=docente.correo_institucional,
        contexto={
            "docente": f"{docente.nombres} {docente.apellidos}".strip(),
            "numero_solicitud": solicitud.id,
            "asignatura": solicitud.seccion.asignatura.nombre,
            "nrc": solicitud.seccion.nrc,
            "institucion": solicitud.institucion_receptora,
            "persona_receptora": solicitud.persona_receptora,
        },
        carta_documento=documento,
    )
