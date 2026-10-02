import hashlib
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from archivos.services import guardar_archivo

from .models import CartaDocumento


def generar_pdf_carta(solicitud, usuario):
    if solicitud.estado != "APROBADA":
        raise ValueError("La solicitud debe estar aprobada.")

    estudiantes = list(
        solicitud.estudiantes.order_by("orden")
    )

    if not estudiantes:
        raise ValueError(
            "La solicitud no tiene estudiantes asociados."
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

    fecha = solicitud.fecha_aprobacion or timezone.now()

    docente = solicitud.docente_derivador
    nombre_docente = (
        f"{docente.nombres} {docente.apellidos}"
    ).strip()

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
            Spacer(1, 30),
            Paragraph(
                "<b>Coordinación Aprendizaje + Servicio</b>",
                cuerpo,
            ),
            Paragraph(
                "Universidad Autónoma de Chile",
                cuerpo,
            ),
        ]
    )

    documento.build(contenido)

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
            tipo="PDF",
            fecha_generacion=timezone.now(),
            hash_documento=hash_documento,
        )

    return carta_documento