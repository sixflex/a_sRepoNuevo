"""
Acuerdo formal para firmar (actividad 11 de la Ruta, "Firmar el Acuerdo Formal").

El docente llena el acuerdo en el portal (formulario
FORMALIZACION_ACUERDOS_AS_2026), lo descarga en PDF con el formato de la
Coordinación (el mismo de la planilla "Formulario A+S de Acuerdo con SC"
de la Ruta de Jorge), lo imprimen, lo firman todos y sube el escaneado.
También puede bajar el formato en blanco para llenarlo a mano.

No guarda nada: el PDF se arma cada vez desde la respuesta del formulario.
"""

import re
import unicodedata
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from encuestas import constantes as c
from encuestas.models import RespuestaFormulario
from encuestas.precarga import FORMALIZACION_ACUERDOS
from encuestas.services import resumen_respuesta

ROJO = colors.HexColor("#C8102E")
GRIS = colors.HexColor("#F2F4F7")
BORDE = colors.HexColor("#D0D5DD")
FILAS_ESTUDIANTES_EN_BLANCO = 6


FIRMANTES = {
    "nombre del docente firmante": "docente",
    "nombre del socio comunitario firmante": "socio",
    "nombre del director/a de carrera": "director",
    "nombres de los estudiantes firmantes": "estudiantes",
}
FECHA = "fecha del acuerdo"


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return " ".join(texto.lower().split())


def _rol_firma(texto):
    normal = _normalizar(texto)
    if normal.startswith(FECHA):
        return "fecha"
    return FIRMANTES.get(normal)


def acuerdos_de(seccion):
    """Acuerdos llenados para la sección, del más antiguo al más nuevo."""
    return list(
        RespuestaFormulario.objects
        .filter(seccion=seccion, version__plantilla__codigo=FORMALIZACION_ACUERDOS)
        .select_related("equipo", "socio")
        .order_by("fecha_envio", "id")
    )


def nombre_acuerdo(respuesta, numero):
    """Texto del botón de descarga: "Acuerdo 1 · Grupo 2" o con el socio."""
    detalle = ""
    if respuesta.equipo_id:
        detalle = f" · Grupo {respuesta.equipo.numero_grupo}"
    elif respuesta.socio_id:
        detalle = f" · {respuesta.socio}"
    return f"Acuerdo {numero}{detalle}"


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("titulo", parent=base["Title"], fontSize=16, textColor=ROJO, alignment=0, spaceAfter=0),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=10, textColor=colors.HexColor("#475467"), spaceAfter=8),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontSize=11, textColor=ROJO, spaceBefore=10, spaceAfter=4),
        "etiqueta": ParagraphStyle("etiqueta", parent=base["Normal"], fontSize=9, leading=11, fontName="Helvetica-Bold"),
        "celda": ParagraphStyle("celda", parent=base["Normal"], fontSize=9.5, leading=12.5),
        "pie": ParagraphStyle("pie", parent=base["Normal"], fontSize=8, textColor=colors.HexColor("#667085"), alignment=1),
        "firma": ParagraphStyle("firma", parent=base["Normal"], fontSize=9, leading=11, alignment=1),
    }


def _p(texto, estilo):
    return Paragraph(escape(str(texto or "")).replace("\n", "<br/>"), estilo)


def _bloques(version, respuesta):
    """
    [(título del bloque, [(pregunta, texto, es_largo)])] sin las preguntas de
    firmas, y {rol: texto} con los firmantes y la fecha.
    """
    if respuesta is not None:
        pares = resumen_respuesta(respuesta)
    else:
        pares = [
            (pregunta, "")
            for pregunta in version.preguntas.select_related("bloque").order_by("bloque__orden", "orden", "id")
        ]
    bloques, firmas, por_titulo = [], {}, {}
    for pregunta, texto in pares:
        rol = _rol_firma(pregunta.texto)
        if rol:
            firmas[rol] = texto if texto not in (None, "—") else ""
            continue
        titulo = pregunta.bloque.titulo if pregunta.bloque_id else ""
        if titulo not in por_titulo:
            por_titulo[titulo] = []
            bloques.append((titulo, por_titulo[titulo]))
        por_titulo[titulo].append((pregunta.texto, texto, pregunta.tipo == c.TEXTO_LARGO))
    return bloques, firmas


def _tabla_bloque(filas, estilos, en_blanco):
    datos = []
    for texto, valor, es_largo in filas:
        celda = _p(valor, estilos["celda"]) if not en_blanco else Spacer(1, 2.2 * cm if es_largo else 0.5 * cm)
        datos.append([_p(texto, estilos["etiqueta"]), celda])
    tabla = Table(datos, colWidths=[5.2 * cm, 11.8 * cm])
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("BACKGROUND", (0, 0), (0, -1), GRIS),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabla


def _recuadro_firma(cargo, nombre, estilos):
    """Espacio para firmar, una línea y debajo el cargo y el nombre."""
    texto = f"<b>{escape(cargo)}</b>" + (f"<br/>{escape(nombre)}" if nombre else "<br/>Nombre: ______________________")
    return [Spacer(1, 1.6 * cm), Paragraph("_" * 34, estilos["firma"]), Paragraph(texto, estilos["firma"])]


def _firmas(firmas, estilos):
    principales = Table(
        [
            [_recuadro_firma("Firma Docente", firmas.get("docente"), estilos),
             _recuadro_firma("Firma Socio Comunitario", firmas.get("socio"), estilos)],
            [_recuadro_firma("Firma Director/a de Carrera", firmas.get("director"), estilos), ""],
        ],
        colWidths=[8.5 * cm, 8.5 * cm],
    )
    principales.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))

    nombres = [n.strip(" -•\t") for n in re.split(r"[\n;,]+", firmas.get("estudiantes") or "") if n.strip(" -•\t")]
    filas = [["Estudiante", "Firma"]] + [[n, ""] for n in nombres]
    filas += [["", ""]] * max(0, (FILAS_ESTUDIANTES_EN_BLANCO if not nombres else 0))
    tabla = Table(
        [[_p(a, estilos["etiqueta"] if i == 0 else estilos["celda"]), _p(b, estilos["etiqueta"] if i == 0 else estilos["celda"])]
         for i, (a, b) in enumerate(filas)],
        colWidths=[9 * cm, 8 * cm],
        rowHeights=[None] + [0.9 * cm] * (len(filas) - 1),
        repeatRows=1,
    )
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, BORDE),
        ("BACKGROUND", (0, 0), (-1, 0), GRIS),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return principales, [Spacer(1, 0.5 * cm), Paragraph("Firmas de los estudiantes", estilos["h2"]), tabla]


def construir_pdf_acuerdo(seccion, version, respuesta=None):
    """PDF del acuerdo: con lo que llenó el docente o, sin respuesta, en blanco."""
    from cartas.plantilla_oficial import _imagen, recursos_carta

    estilos = _estilos()
    en_blanco = respuesta is None
    bloques, firmas = _bloques(version, respuesta)

    contenido = []
    logo = _imagen(recursos_carta().get("logo"), 3.2 * cm, 2.2 * cm, alineacion="RIGHT")
    if logo is not None:
        contenido.append(logo)
    contenido += [
        Paragraph("FORMALIZACIÓN DE ACUERDOS", estilos["titulo"]),
        Paragraph("Socio Comunitario · Socio Académico · Programa Aprendizaje + Servicio", estilos["sub"]),
    ]
    periodo = f" · {seccion.periodo}" if getattr(seccion, "periodo_id", None) else ""
    contenido.append(_p(
        f"{seccion.asignatura.nombre} · NRC {seccion.nrc} · Sección {seccion.seccion}{periodo}",
        estilos["celda"],
    ))

    for numero, (titulo, filas) in enumerate(bloques, start=1):
        contenido.append(KeepTogether([
            Paragraph(f"{numero} · {escape(titulo.upper())}", estilos["h2"]),
            _tabla_bloque(filas, estilos, en_blanco),
        ]))

    principales, estudiantes = _firmas(firmas, estilos)
    fecha = firmas.get("fecha") or ("____ / ____ / ________" if en_blanco else "")
    contenido.append(KeepTogether([
        Paragraph(f"{len(bloques) + 1} · FECHA Y FIRMAS", estilos["h2"]),
        _p(f"Fecha de formalización: {fecha}", estilos["celda"]),
        Spacer(1, 0.2 * cm),
        _p(
            "Este acuerdo se firma antes de ejecutar el servicio. El documento firmado se sube a la Ruta "
            "del Docente y se entrega a la Coordinación A+S al final del semestre.",
            estilos["pie"],
        ),
        principales,
    ]))
    contenido += estudiantes

    def pie(lienzo, documento):
        lienzo.saveState()
        lienzo.setFont("Helvetica", 7.5)
        lienzo.setFillColor(colors.HexColor("#667085"))
        lienzo.drawCentredString(
            A4[0] / 2, 1.1 * cm,
            f"Universidad Autónoma de Chile · Programa Aprendizaje + Servicio · página {documento.page}",
        )
        lienzo.restoreState()

    salida = BytesIO()
    SimpleDocTemplate(
        salida, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.5 * cm, bottomMargin=1.8 * cm,
        title="Acuerdo formal A+S", author="Portal A+S",
    ).build(contenido, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
