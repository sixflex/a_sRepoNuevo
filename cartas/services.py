import hashlib
import logging
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from archivos.services import guardar_archivo
from auditoria.services import registrar_auditoria
from comunicaciones.services import EmailService

from .models import CartaDocumento, SolicitudCarta


MAX_ALUMNOS_POR_CARTA = 6
MESES_ANTIGUEDAD_ALERTA = 12
CODIGO_PLANTILLA_CARTA = "CARTA_PRESENTACION_DOCENTE"

logger = logging.getLogger(__name__)

FIRMA_ANCHO_MAX = 5 * cm
FIRMA_ALTO_MAX = 2.5 * cm


def _cargar_firma_prueba():
    """
    Devuelve la firma de prueba como flowable de ReportLab, o None.

    La ruta viene de settings.CARTA_FIRMA_PRUEBA_PATH (variable de entorno
    en el .env). El archivo vive fuera del repositorio y fuera de static/media:
    solo se lee en el servidor y se incrusta en el PDF, nunca se sirve por URL.
    """
    ruta = getattr(settings, "CARTA_FIRMA_PRUEBA_PATH", "") or ""
    if not ruta:
        return None

    archivo = Path(ruta).expanduser()
    if not archivo.is_file():
        logger.warning(
            "La firma de prueba configurada no existe: %s. "
            "La carta se genera sin firma.",
            archivo,
        )
        return None

    try:
        datos = archivo.read_bytes()
        ancho, alto = ImageReader(BytesIO(datos)).getSize()
        escala = min(FIRMA_ANCHO_MAX / ancho, FIRMA_ALTO_MAX / alto)
        firma = Image(
            BytesIO(datos),
            width=ancho * escala,
            height=alto * escala,
        )
    except Exception:
        logger.warning(
            "No se pudo leer la firma de prueba (%s). "
            "La carta se genera sin firma.",
            archivo,
            exc_info=True,
        )
        return None

    firma.hAlign = "LEFT"
    return firma


def verificar_alerta_antiguedad_socio(socio):

    if not socio:
        return False

    hace_un_ano = timezone.now().date() - timedelta(days=365)
    ultima_participacion = socio.participaciones.order_by("-fecha_inicio").first()

    if not ultima_participacion or not ultima_participacion.fecha_inicio:
        return True

    return ultima_participacion.fecha_inicio < hace_un_ano


def _agregar_marca_de_agua(canvas, doc):
    """Marca de agua institucional discreta para el PDF."""
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 50)
    canvas.setFillColor(colors.HexColor("#F1F5F9"))
    canvas.translate(A4[0] / 2.0, A4[1] / 2.0)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "APRENDIZAJE + SERVICIO")
    canvas.restoreState()


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

    buffer = BytesIO()

    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    estilos = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "TituloCarta",
        parent=estilos["Heading1"],
        alignment=TA_CENTER,
        fontSize=14,
        leading=18,
        spaceAfter=24,
    )

    cuerpo = ParagraphStyle(
        "CuerpoCarta",
        parent=estilos["Normal"],
        fontSize=11,
        leading=17,
        spaceAfter=12,
    )

    pie_estilo = ParagraphStyle(
        "PieEstilo",
        parent=estilos["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748B"),
    )

    fecha = solicitud.fecha_aprobacion or timezone.now()

    docente = solicitud.docente_derivador
    nombre_docente = (
        f"{docente.nombres} {docente.apellidos}"
    ).strip() if docente else ""

    contenido = [
        Paragraph(
            "<b>CARTA PRESENTACIÓN</b>",
            titulo,
        ),
        Paragraph(
            f"Santiago, {fecha.strftime('%d/%m/%Y')}",
            cuerpo,
        ),
        Spacer(1, 8),
        Paragraph(
            f"<b>Señor(a):</b> {solicitud.persona_receptora}",
            cuerpo,
        ),
        Paragraph(
            f"<b>Institución:</b> {solicitud.institucion_receptora}",
            cuerpo,
        ),
        Spacer(1, 8),
        Paragraph(
            (
                "Junto con saludar, por medio de la presente "
                "se presenta a los estudiantes que participan "
                "en una actividad de Aprendizaje + Servicio "
                f"correspondiente a la asignatura "
                f"<b>{solicitud.seccion.asignatura.nombre}</b>, "
                f"impartida por el docente "
                f"<b>{nombre_docente}</b>."
            ),
            cuerpo,
        ),
        Paragraph(
            (
                "Los estudiantes desarrollarán actividades "
                "vinculadas con la metodología de "
                "Aprendizaje + Servicio en colaboración con "
                "la institución receptora."
            ),
            cuerpo,
        ),
        Spacer(1, 12),
    ]

    datos_tabla = [
        [
            Paragraph("<b>Nombre</b>", cuerpo),
            Paragraph("<b>RUT</b>", cuerpo),
        ]
    ]

    for estudiante in estudiantes:
        datos_tabla.append(
            [
                estudiante.nombre,
                estudiante.rut,
            ]
        )

    tabla = Table(
        datos_tabla,
        colWidths=[
            11 * cm,
            4 * cm,
        ],
        repeatRows=1,
    )

    tabla.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    contenido.append(tabla)
    contenido.append(Spacer(1, 24))

    if solicitud.consideraciones:
        contenido.append(
            Paragraph(
                (
                    "<b>Consideraciones:</b> "
                    f"{solicitud.consideraciones}"
                ),
                cuerpo,
            )
        )

    firma = _cargar_firma_prueba()

    contenido.extend(
        [
            Spacer(1, 12),
            Paragraph(
                (
                    "Agradecemos desde ya la disposición y "
                    "colaboración brindada para el desarrollo "
                    "de esta experiencia de Aprendizaje + Servicio."
                ),
                cuerpo,
            ),
            Spacer(1, 12),
            firma if firma is not None else Spacer(1, 18),
            Paragraph(
                "<b>Coordinación Aprendizaje + Servicio</b>",
                cuerpo,
            ),
            Paragraph(
                "Universidad Autónoma de Chile",
                cuerpo,
            ),
            Spacer(1, 20),
        ]
    )

  
    codigo_verificacion = f"CDE-{solicitud.id}-{fecha.strftime('%Y%m%d')}"
    contenido.append(
        Paragraph(
            f"<b>Documento Validado Digitalmente</b><br/>"
            f"<b>Código de Verificación:</b> {codigo_verificacion}<br/>"
            f"<b>Emitido por:</b> {usuario.get_full_name() or usuario.username}",
            pie_estilo,
        )
    )

    documento.build(
        contenido,
        onFirstPage=_agregar_marca_de_agua,
        onLaterPages=_agregar_marca_de_agua,
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()

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

    socio = getattr(solicitud, "socio", None)
    alerta_antiguedad = verificar_alerta_antiguedad_socio(socio)

    lotes = [
        todos_estudiantes[i : i + MAX_ALUMNOS_POR_CARTA]
        for i in range(0, len(todos_estudiantes), MAX_ALUMNOS_POR_CARTA)
    ]

    cartas_generadas = []
    for lote in lotes:
        carta_doc = generar_pdf_carta(solicitud, usuario, estudiantes=lote)
        cartas_generadas.append(carta_doc)

    return {
        "cartas": cartas_generadas,
        "total_cartas": len(cartas_generadas),
        "alerta_antiguedad": alerta_antiguedad,
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