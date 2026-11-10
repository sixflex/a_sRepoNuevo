"""
Ficha del proyecto A+S (RF-EVI-01): todo lo de una sección en un PDF.

Junta lo que ya está en el sistema, sin pedir nada nuevo al docente: datos
de la sección, grupos con su socio y proyecto, avance de la Ruta por etapa,
las respuestas de los formularios llenados desde la Ruta y las evidencias.
Va dentro del ZIP que descarga el Coordinador.
"""

from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from encuestas.models import RespuestaFormulario
from encuestas.services import resumen_respuesta
from proyectos.models import Equipo

from .models import SeccionActividad
from .paso_a_paso import FORMULARIO_POR_ORDEN, armar_etapas

ENCUESTAS = {
    "EVALUACION_AS_ESTUDIANTES": "estudiantes",
    "EVALUACION_AS_SOCIOS": "socios comunitarios",
    "EVALUACION_AS_DOCENTES": "docentes",
}

NOMBRE_PDF = "Ficha del proyecto.pdf"
ROJO = colors.HexColor("#C8102E")
GRIS = colors.HexColor("#F2F4F7")
BORDE = colors.HexColor("#D0D5DD")


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Title"], fontSize=18, textColor=ROJO, alignment=0, spaceAfter=2),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=10, textColor=colors.HexColor("#475467"), spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=12.5, textColor=colors.HexColor("#101828"), spaceBefore=12, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontSize=10.5, spaceBefore=8, spaceAfter=4),
        "celda": ParagraphStyle("celda", parent=base["Normal"], fontSize=8.8, leading=11),
        "celda_b": ParagraphStyle("celda_b", parent=base["Normal"], fontSize=8.8, leading=11, fontName="Helvetica-Bold"),
        "nota": ParagraphStyle("nota", parent=base["Normal"], fontSize=8.5, textColor=colors.HexColor("#667085")),
    }


def _p(texto, estilo):
    return Paragraph(escape(str(texto if texto not in (None, "") else "—")).replace("\n", "<br/>"), estilo)


def _tabla(filas, anchos, estilos, encabezado=True):
    datos = [
        [_p(celda, estilos["celda_b"] if (encabezado and i == 0) else estilos["celda"]) for celda in fila]
        for i, fila in enumerate(filas)
    ]
    tabla = Table(datos, colWidths=anchos, repeatRows=1 if encabezado else 0)
    estilo = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if encabezado:
        estilo.append(("BACKGROUND", (0, 0), (-1, 0), GRIS))
    else:
        estilo.append(("BACKGROUND", (0, 0), (0, -1), GRIS))
    tabla.setStyle(TableStyle(estilo))
    return tabla


def actividades_de(seccion_ruta):
    return list(
        SeccionActividad.objects
        .filter(seccion_ruta=seccion_ruta)
        .select_related("ruta_actividad")
        .prefetch_related("evidencias__archivo")
        .order_by("ruta_actividad__orden")
    )


def generar_ficha_pdf(seccion_ruta):
    """Bytes del PDF de la ficha del proyecto de la sección."""
    seccion = seccion_ruta.seccion
    e = _estilos()
    ancho = A4[0] - 3.6 * cm
    historia = [
        Paragraph("Ficha del proyecto A+S", e["titulo"]),
        _p(f"{seccion.asignatura.nombre} · NRC {seccion.nrc} · Sección {seccion.seccion}", e["sub"]),
    ]

    docentes = ", ".join(f"{d.nombres} {d.apellidos}" for d in seccion.docentes.all())
    carreras = ", ".join(c.nombre for c in seccion.carreras.all())
    historia += [
        Paragraph("Datos de la sección", e["h2"]),
        _tabla([
            ["Asignatura", seccion.asignatura.nombre],
            ["Docente", docentes],
            ["Carrera", carreras],
            ["Campus", f"{seccion.campus.nombre} ({seccion.campus.sede.nombre})"],
            ["Período", seccion.periodo.nombre],
            ["Avance de la Ruta", f"{seccion_ruta.porcentaje_final or 0:.0f} % · {'Completada' if seccion_ruta.estado == 'COMPLETADA' else 'En progreso'}"],
        ], [4.2 * cm, ancho - 4.2 * cm], e, encabezado=False),
    ]

    equipos = (
        Equipo.objects.filter(seccion=seccion)
        .select_related("proyecto")
        .con_socio_vigente()
        .prefetch_related("integrantes")
        .order_by("numero_grupo")
    )
    historia.append(Paragraph("Grupos", e["h2"]))
    if equipos:
        filas = [["Grupo", "Proyecto", "Socio comunitario", "Integrantes"]]
        for equipo in equipos:
            socio = equipo.socio_vigente
            filas.append([
                f"Grupo {equipo.numero_grupo}",
                equipo.proyecto.nombre if equipo.proyecto_id else "",
                socio.nombre_organizacion if socio else "Sin socio registrado",
                str(len(equipo.integrantes.all())),
            ])
        historia.append(_tabla(filas, [2 * cm, 5.6 * cm, 6 * cm, ancho - 13.6 * cm], e))
    else:
        historia.append(_p("Aún no hay grupos registrados.", e["nota"]))

    actividades = actividades_de(seccion_ruta)
    etapas, _ = armar_etapas(actividades)
    historia.append(Paragraph("Avance por etapa", e["h2"]))
    filas = [["Etapa", "Hechas", "Archivos", "Pendientes"]]
    for etapa in etapas:
        filas.append([
            f"{etapa['numero']}. {etapa['nombre']}",
            f"{etapa['hechas']} de {etapa['total']}",
            str(etapa["archivos"]),
            "\n".join(f"{a.ruta_actividad.orden}. {a.ruta_actividad.nombre}" for a in etapa["pendientes"]) or "Nada pendiente",
        ])
    historia.append(_tabla(filas, [5 * cm, 2 * cm, 2 * cm, ancho - 9 * cm], e))

    # Solo los formularios de la Ruta; las encuestas de satisfacción van como conteo
    # (las de estudiantes son anónimas).
    respuestas = (
        RespuestaFormulario.objects
        .filter(seccion=seccion, version__plantilla__codigo__in=set(FORMULARIO_POR_ORDEN.values()))
        .select_related("version__plantilla", "equipo")
        .order_by("fecha_envio", "id")
    )
    historia.append(Paragraph("Formularios llenados", e["h2"]))
    if not respuestas:
        historia.append(_p("Todavía no se ha llenado ningún formulario desde la Ruta.", e["nota"]))
    for respuesta in respuestas:
        titulo = respuesta.version.plantilla.titulo
        if respuesta.equipo_id:
            titulo += f" · Grupo {respuesta.equipo.numero_grupo}"
        fecha = timezone.localtime(respuesta.fecha_envio).strftime("%d/%m/%Y")
        historia.append(_p(f"{titulo} ({fecha})", e["h3"]))
        filas = [[pregunta.texto, texto] for pregunta, texto in resumen_respuesta(respuesta) if texto]
        if filas:
            historia.append(_tabla(filas, [6.5 * cm, ancho - 6.5 * cm], e, encabezado=False))

    conteo = {
        codigo: RespuestaFormulario.objects.filter(seccion=seccion, version__plantilla__codigo=codigo).count()
        for codigo in ENCUESTAS
    }
    historia.append(Paragraph("Encuestas de satisfacción", e["h2"]))
    historia.append(_tabla(
        [["Encuesta", "Respuestas"]] + [[f"Encuesta {nombre}", str(conteo[codigo])] for codigo, nombre in ENCUESTAS.items()],
        [8 * cm, 3 * cm], e,
    ))

    historia.append(Paragraph("Evidencias", e["h2"]))
    filas = [["Actividad", "Archivo", "Descripción"]]
    for actividad in actividades:
        for evidencia in actividad.evidencias.all():
            filas.append([
                f"{actividad.ruta_actividad.orden}. {actividad.ruta_actividad.nombre}",
                evidencia.archivo.nombre_original,
                evidencia.descripcion or "",
            ])
    if len(filas) > 1:
        historia.append(_tabla(filas, [6 * cm, 6 * cm, ancho - 12 * cm], e))
        historia.append(Spacer(1, 4))
        historia.append(_p("Los archivos están en las carpetas de cada etapa de este ZIP.", e["nota"]))
    else:
        historia.append(_p("Aún no hay evidencias subidas.", e["nota"]))

    historia.append(Spacer(1, 10))
    historia.append(_p(f"Generada el {timezone.localtime().strftime('%d/%m/%Y %H:%M')} desde el Portal A+S.", e["nota"]))

    salida = BytesIO()
    documento = SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.6 * cm, bottomMargin=1.6 * cm,
        title="Ficha del proyecto A+S", author="Portal A+S",
    )
    documento.build(historia)
    return salida.getvalue()
