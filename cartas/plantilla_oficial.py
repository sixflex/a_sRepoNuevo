"""
Carta de Presentación con el formato oficial de Coordinación A+S.

El Coordinador genera hoy sus cartas con una plantilla de Word y
"combinar correspondencia" (CARTA Presentación para Estudiantes a SC.docx):
logo de la UA arriba a la derecha, el mismo texto para todas, una tabla
Nombre | RUT y abajo su firma y su tarjeta de contacto. Aquí se arma el PDF
con ese mismo formato y los datos de la solicitud.

De la planilla Word solo se toman las imágenes:
  - logo: la imagen del encabezado;
  - firma y tarjeta: la 1.ª y la 2.ª imagen del cuerpo, en ese orden.

La planilla contiene la firma real, así que NUNCA va en el repositorio ni en
static/media (RN-07). El Coordinador la sube en Configuración → Carta oficial
(PlantillaCarta, almacenamiento privado). Como respaldo se puede indicar una
ruta en el .env con CARTA_PLANTILLA_PATH (en Render, como "Secret File"). Si
no hay ninguna, el logo sale de static/img y la firma de
CARTA_FIRMA_PRUEBA_PATH (firma de prueba).
"""

import logging
import posixpath
import re
import zipfile
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable, Image, KeepInFrame, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

logger = logging.getLogger(__name__)

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# Medidas de la planilla Word (márgenes 3 cm, superior 2,5 cm).
LOGO_ANCHO, LOGO_ALTO = 3.2 * cm, 2.5 * cm
FIRMA_ANCHO, FIRMA_ALTO = 6.2 * cm, 2.6 * cm
TARJETA_ANCHO, TARJETA_ALTO = 7.6 * cm, 3.6 * cm

# ---------------------------------------------------------------------------
# Imágenes de la planilla
# ---------------------------------------------------------------------------

def _rels(zf, parte):
    """{rId: ruta dentro del zip} para una parte de Word (document.xml, header1.xml…)."""
    carpeta, nombre = posixpath.split(parte)
    ruta_rels = posixpath.join(carpeta, "_rels", f"{nombre}.rels")
    if ruta_rels not in zf.namelist():
        return {}
    xml = zf.read(ruta_rels).decode("utf-8")
    rels = {}
    for atributos in re.findall(r"<Relationship\b([^>]*)/?>", xml):
        rid = re.search(r'Id="([^"]+)"', atributos)
        destino = re.search(r'Target="([^"]+)"', atributos)
        if rid and destino and "TargetMode=\"External\"" not in atributos:
            rels[rid.group(1)] = posixpath.normpath(posixpath.join(carpeta, destino.group(1)))
    return rels


def _recortar(datos, recorte):
    """Aplica el recorte que Word guarda en <a:srcRect> (milésimas de %)."""
    if not any(recorte.values()):
        return datos
    from PIL import Image as PilImage

    imagen = PilImage.open(BytesIO(datos))
    ancho, alto = imagen.size
    caja = (
        round(ancho * recorte["l"] / 100000),
        round(alto * recorte["t"] / 100000),
        round(ancho * (1 - recorte["r"] / 100000)),
        round(alto * (1 - recorte["b"] / 100000)),
    )
    if caja[0] >= caja[2] or caja[1] >= caja[3]:
        return datos
    imagen.info.pop("transparency", None)
    salida = BytesIO()
    imagen.convert("RGBA" if imagen.mode in ("RGBA", "LA") else "RGB").crop(caja).save(salida, format="PNG")
    return salida.getvalue()


def _imagenes_en_orden(zf, parte):
    """Bytes de las imágenes de una parte, en orden y con el recorte que les hizo Word."""
    if parte not in zf.namelist():
        return []
    xml = zf.read(parte).decode("utf-8")
    rels = _rels(zf, parte)
    imagenes = []
    for bloque in re.findall(r"<a:blip\b.*?(?:</pic:blipFill>|$)", xml, re.S):
        rid = re.search(r'r:embed="([^"]+)"', bloque)
        ruta = rels.get(rid.group(1)) if rid else None
        if not ruta or ruta not in zf.namelist():
            continue
        recorte = {lado: 0 for lado in "ltrb"}
        rect = re.search(r"<a:srcRect\b([^>]*)/?>", bloque)
        if rect:
            for lado, valor in re.findall(r'\b([ltrb])="(-?\d+)"', rect.group(1)):
                recorte[lado] = max(int(valor), 0)
        try:
            imagenes.append(_recortar(zf.read(ruta), recorte))
        except Exception:
            imagenes.append(zf.read(ruta))
    return imagenes


def leer_imagenes_planilla(contenido):
    """
    Saca logo, firma y tarjeta de una planilla .docx (bytes).

    Devuelve {"logo": bytes|None, "firma": bytes|None, "tarjeta": bytes|None}.
    Lanza ValueError si el archivo no es un Word válido.
    """
    try:
        zf = zipfile.ZipFile(BytesIO(contenido))
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo no es un documento Word (.docx) válido.") from exc

    with zf:
        cuerpo = _imagenes_en_orden(zf, "word/document.xml")
        encabezados = sorted(n for n in zf.namelist() if re.fullmatch(r"word/header\d+\.xml", n))
        logo = next((img for parte in encabezados for img in _imagenes_en_orden(zf, parte)), None)

    return {
        "logo": logo,
        "firma": cuerpo[0] if len(cuerpo) >= 1 else None,
        "tarjeta": cuerpo[1] if len(cuerpo) >= 2 else None,
    }


@lru_cache(maxsize=4)
def _imagenes_planilla_cacheadas(ruta, _mtime):
    return leer_imagenes_planilla(Path(ruta).read_bytes())


def _leer_archivo(ruta):
    archivo = Path(ruta).expanduser()
    if not archivo.is_file():
        logger.warning("No existe el archivo configurado para la carta: %s", archivo)
        return None
    return archivo.read_bytes()


@lru_cache(maxsize=4)
def _imagenes_archivo_cacheadas(archivo_id, _hash):
    from archivos.models import Archivo
    from archivos.services import abrir_archivo

    with abrir_archivo(Archivo.objects.get(pk=archivo_id)) as contenido:
        return leer_imagenes_planilla(contenido.read())


def plantilla_activa():
    """La carta oficial que subió el Coordinador y está en uso, o None."""
    from .models import PlantillaCarta

    try:
        return PlantillaCarta.objects.select_related("archivo").filter(activa=True).first()
    except Exception:  # tabla aún sin migrar: se sigue con el respaldo
        logger.warning("No se pudo consultar la carta oficial activa.", exc_info=True)
        return None


def imagenes_de_plantilla(plantilla):
    archivo = plantilla.archivo
    return _imagenes_archivo_cacheadas(archivo.pk, archivo.hash_sha256)


def recursos_carta():
    """
    Logo, firma y tarjeta que usará la carta, y la PlantillaCarta de donde
    salieron (o None).

    Orden: carta oficial subida al portal (PlantillaCarta activa) → planilla
    del servidor (CARTA_PLANTILLA_PATH) → firma de prueba
    (CARTA_FIRMA_PRUEBA_PATH) → logo de static/img. Lo que falte queda None.
    """
    recursos = {"logo": None, "firma": None, "tarjeta": None, "plantilla": None}

    plantilla = plantilla_activa()
    if plantilla is not None:
        try:
            recursos.update({k: v for k, v in imagenes_de_plantilla(plantilla).items() if v})
            recursos["plantilla"] = plantilla
        except Exception:
            logger.warning("No se pudo leer la carta oficial subida (id %s).", plantilla.pk, exc_info=True)

    ruta_planilla = getattr(settings, "CARTA_PLANTILLA_PATH", "") or ""
    if ruta_planilla and recursos["plantilla"] is None:
        archivo = Path(ruta_planilla).expanduser()
        if archivo.is_file():
            try:
                recursos.update(
                    {k: v for k, v in _imagenes_planilla_cacheadas(str(archivo), archivo.stat().st_mtime).items() if v}
                )
            except Exception:
                logger.warning("No se pudo leer la planilla de la carta: %s", archivo, exc_info=True)
        else:
            logger.warning("La planilla de la carta configurada no existe: %s", archivo)

    if recursos["firma"] is None and getattr(settings, "CARTA_FIRMA_PRUEBA_PATH", ""):
        recursos["firma"] = _leer_archivo(settings.CARTA_FIRMA_PRUEBA_PATH)

    if recursos["logo"] is None:
        ruta_logo = finders.find("img/escudo_ua.png")
        if ruta_logo:
            recursos["logo"] = Path(ruta_logo).read_bytes()

    return recursos


def _limpiar(datos):
    """
    Deja la imagen en RGB sobre fondo blanco puro.

    Word muestra las imágenes con sus propios efectos (la firma escaneada trae
    un gris de fondo y una transparencia rara en la paleta); en el PDF se ven
    como cajas grises. Se quita la transparencia y el casi-blanco pasa a blanco.
    """
    from PIL import Image as PilImage

    imagen = PilImage.open(BytesIO(datos))
    imagen.info.pop("transparency", None)
    if imagen.mode in ("RGBA", "LA"):
        fondo = PilImage.new("RGB", imagen.size, "white")
        fondo.paste(imagen, mask=imagen.getchannel("A"))
        imagen = fondo
    imagen = imagen.convert("RGB")
    imagen = imagen.point(lambda valor: 255 if valor >= 230 else valor)
    salida = BytesIO()
    imagen.save(salida, format="PNG")
    return salida.getvalue()


def _imagen(datos, ancho_max, alto_max, alineacion="CENTER", fondo_transparente=False):
    """Imagen de ReportLab que cabe en la caja, o None si no se puede leer."""
    if not datos:
        return None
    try:
        datos = _limpiar(datos)
        ancho, alto = ImageReader(BytesIO(datos)).getSize()
        escala = min(ancho_max / ancho, alto_max / alto)
        imagen = Image(
            BytesIO(datos),
            width=ancho * escala,
            height=alto * escala,
            # El blanco no tapa lo que hay debajo (la firma va sobre la tarjeta).
            mask=[255, 255, 255, 255, 255, 255] if fondo_transparente else None,
        )
    except Exception:
        logger.warning("No se pudo leer una imagen de la carta.", exc_info=True)
        return None
    imagen.hAlign = alineacion
    return imagen


class FirmaConTarjeta(Flowable):
    """Firma encima de la tarjeta, montada sobre ella como en la planilla Word."""

    TRASLAPE = 0.35  # parte de la firma que queda sobre la tarjeta

    def __init__(self, firma, tarjeta):
        super().__init__()
        self.firma = firma
        self.tarjeta = tarjeta
        self.width = max(firma.drawWidth, tarjeta.drawWidth)
        self.height = tarjeta.drawHeight + firma.drawHeight * (1 - self.TRASLAPE)
        self.hAlign = "CENTER"

    def draw(self):
        self.tarjeta.drawOn(self.canv, (self.width - self.tarjeta.drawWidth) / 2, 0)
        self.firma.drawOn(
            self.canv,
            (self.width - self.firma.drawWidth) / 2,
            self.tarjeta.drawHeight - self.firma.drawHeight * self.TRASLAPE,
        )


# ---------------------------------------------------------------------------
# Texto y PDF
# ---------------------------------------------------------------------------

def fecha_carta(fecha):
    """'Santiago, 2 de septiembre de 2026'."""
    return f"Santiago, {fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def _texto(valor):
    """Escapa lo que escribe el usuario para que ReportLab no lo lea como etiqueta."""
    return (
        str(valor or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .strip()
    )


def _marca_borrador(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica-Bold", 90)
    canvas.setFillColor(colors.HexColor("#E2E8F0"))
    canvas.translate(LETTER[0] / 2.0, LETTER[1] / 2.0)
    canvas.rotate(45)
    canvas.drawCentredString(0, 0, "BORRADOR")
    canvas.restoreState()


def _proteccion():
    """
    Carta final de solo lectura: se puede abrir, imprimir y copiar texto, pero
    no editar, anotar ni rellenar sin la clave de propietario, que solo conoce
    el servidor (derivada de SECRET_KEY, nunca se guarda ni se muestra).

    Es la restricción estándar de PDF (AES-128). Impide modificarla en Acrobat,
    Edge o Chrome; no es una firma electrónica avanzada (fuera de alcance, 2.2).
    El hash SHA-256 de cada carta queda en CartaDocumento.hash_documento, así
    Coordinación puede comprobar si un PDF que le muestran es el que envió.
    """
    import hashlib

    from reportlab.lib.pdfencrypt import StandardEncryption

    clave = hashlib.sha256(f"carta-pdf:{settings.SECRET_KEY}".encode()).hexdigest()
    return StandardEncryption(
        "", ownerPassword=clave, canPrint=1, canModify=0, canCopy=1, canAnnotate=0, strength=128,
    )


def construir_pdf(*, fecha, persona_receptora, institucion_receptora, asignatura,
                  docente, estudiantes, borrador, recursos=None, proteger=True):
    """
    Devuelve los bytes del PDF con el formato oficial.

    `estudiantes`: lista de (nombre, rut). En borrador no lleva firma ni
    tarjeta y sí una marca "BORRADOR" (RF-CAR-03: la vista previa se
    distingue del documento final firmado).
    """
    recursos = recursos if recursos is not None else recursos_carta()
    # La planilla usa Century Gothic, que no viene en los servidores Linux; se
    # usa Helvetica en todos lados para que la carta salga igual en cualquier PC.
    normal, negrita = "Helvetica", "Helvetica-Bold"

    cuerpo = ParagraphStyle("Cuerpo", fontName=normal, fontSize=11, leading=14, spaceAfter=7)
    justificado = ParagraphStyle("Justificado", parent=cuerpo, alignment=TA_JUSTIFY)
    linea = ParagraphStyle("Linea", parent=cuerpo, spaceAfter=0)
    titulo = ParagraphStyle(
        "Titulo", fontName=negrita, fontSize=14, leading=18, alignment=TA_CENTER, spaceAfter=10,
    )
    celda = ParagraphStyle("Celda", fontName=normal, fontSize=9, leading=11)
    celda_titulo = ParagraphStyle("CeldaTitulo", fontName=negrita, fontSize=11, leading=13)
    aviso = ParagraphStyle(
        "Aviso", fontName=normal, fontSize=9, leading=12, alignment=TA_CENTER,
        textColor=colors.HexColor("#64748B"),
    )

    contenido = []

    logo = _imagen(recursos.get("logo"), LOGO_ANCHO, LOGO_ALTO, alineacion="RIGHT")
    if logo is not None:
        contenido.append(logo)
    contenido += [
        Paragraph("CARTA PRESENTACIÓN", titulo),
        Paragraph(fecha_carta(fecha), cuerpo),
        Spacer(1, 4),
        Paragraph("Señor(a)", linea),
        Paragraph(_texto(persona_receptora), linea),
        Paragraph(_texto(institucion_receptora), linea),
        Paragraph("<u>Presente</u>", cuerpo),
        Spacer(1, 2),
        Paragraph(
            "Por medio de la presente informo a usted que las(os) alumnas(os) de Universidad "
            "Autónoma de Chile que a continuación se detallan, están desarrollando un proyecto "
            f"en la asignatura <b>{_texto(asignatura)}</b> bajo la estricta supervisión de su "
            f"profesor(a) señor(a) <b>{_texto(docente)}</b>, bajo la metodología "
            "Aprendizaje + Servicio.",
            justificado,
        ),
    ]

    filas = [[Paragraph("Nombre", celda_titulo), Paragraph("RUT", celda_titulo)]]
    filas += [[Paragraph(_texto(nombre), celda), Paragraph(_texto(rut), celda)] for nombre, rut in estudiantes]
    ancho_util = LETTER[0] - 6 * cm
    tabla = Table(filas, colWidths=[ancho_util * 0.52, ancho_util * 0.48])
    tabla.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    contenido += [
        tabla,
        Spacer(1, 6),
        Paragraph(
            "Para Universidad Autónoma de Chile será muy grato poder contar con vuestra "
            "colaboración, permitiendo a los estudiantes antes indicados, realizar su "
            "investigación en su prestigiosa institución. El proyecto a desarrollar por los "
            "estudiantes solo tiene fines académicos y su objetivo es entregar un servicio de "
            "calidad a la comunidad.",
            justificado,
        ),
        Paragraph(
            "Como equipo académico nos comprometemos a cumplir todas las condiciones que se "
            "establezcan para no interrumpir el normal funcionamiento de su institución.",
            justificado,
        ),
        Paragraph(
            "Por cualquier consulta o requerimiento no dude en comunicarse con quien suscribe.",
            justificado,
        ),
        Paragraph("Un cordial saludo,", cuerpo),
    ]

    if borrador:
        contenido.append(Spacer(1, 1.2 * cm))
        contenido.append(Paragraph(
            "Vista previa sin firma. La firma y los datos de contacto de Coordinación A+S "
            "se agregan al aprobar la carta.",
            aviso,
        ))
    else:
        firma = _imagen(recursos.get("firma"), FIRMA_ANCHO, FIRMA_ALTO, fondo_transparente=True)
        tarjeta = _imagen(recursos.get("tarjeta"), TARJETA_ANCHO, TARJETA_ALTO)
        if firma is not None and tarjeta is not None:
            contenido.append(FirmaConTarjeta(firma, tarjeta))
        elif firma is not None or tarjeta is not None:
            contenido.append(firma or tarjeta)
        else:
            contenido += [
                Spacer(1, 1.5 * cm),
                Paragraph("<b>Coordinación Aprendizaje + Servicio</b>", linea),
                Paragraph("Universidad Autónoma de Chile", linea),
            ]

    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=3 * cm,
        rightMargin=3 * cm,
        topMargin=1.25 * cm,
        bottomMargin=1.25 * cm,
        title="Carta de Presentación",
        author="Coordinación Aprendizaje + Servicio",
        # La final sale protegida contra cambios; el borrador no hace falta.
        encrypt=_proteccion() if proteger and not borrador else None,
    )
    # La carta oficial ocupa una sola página: si no cabe (nombres muy largos),
    # se achica un poco en vez de pasar la firma a una segunda hoja.
    pagina = KeepInFrame(documento.width, documento.height, contenido, mode="shrink")
    pie = _marca_borrador if borrador else (lambda canvas, doc: None)
    documento.build([pagina], onFirstPage=pie, onLaterPages=pie)
    return buffer.getvalue()
