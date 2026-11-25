"""
Ficha del proyecto A+S (RF-EVI-01): todo lo de una sección.

Junta lo que ya está en el sistema, sin pedir nada nuevo al docente: datos
de la sección, grupos con su socio y proyecto, avance de la Ruta por etapa,
las respuestas de los formularios llenados desde la Ruta y las evidencias.
El Coordinador la ve en el navegador y la exporta a Excel; el PDF va
dentro del ZIP de evidencias.
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


def con_porcentaje_reprobacion(filas):
    """
    La Ruta pide informar el porcentaje de reprobación (y Jorge, también el
    de aprobación); el Resumen solo pregunta estudiantes y reprobados, así
    que se calculan aquí.
    """
    def numero(inicio):
        for texto, valor in filas:
            if texto.startswith(inicio):
                try:
                    return float(str(valor).replace(",", "."))
                except ValueError:
                    return None
        return None

    estudiantes = numero("Cantidad total de estudiantes")
    reprobados = numero("Cantidad de reprobados")
    if not estudiantes or reprobados is None:
        return filas
    def porcentaje(cantidad):
        return f"{cantidad * 100 / estudiantes:.1f}".replace(".", ",") + " %"

    salida = []
    for texto, valor in filas:
        salida.append((texto, valor))
        if texto.startswith("Cantidad de reprobados"):


            salida.append(("Porcentaje de aprobación (calculado)", porcentaje(estudiantes - reprobados)))
            salida.append(("Porcentaje de reprobación (calculado)", porcentaje(reprobados)))
    return salida


def _contacto(socio):
    """«Nombre · cargo · teléfono · correo» del contacto principal del socio."""
    if socio is None:
        return ""
    contacto = socio.contactos.filter(activo=True).order_by("-es_principal", "id").first()
    if contacto is None:
        return ""
    return " · ".join(p for p in (contacto.nombre, contacto.cargo, contacto.telefono, contacto.correo) if p)


def datos_ficha(seccion_ruta):
    """
    Todo lo que muestra la ficha, una sola vez: lo usan la página del
    Coordinador, el Excel y el PDF del ZIP.
    """
    seccion = seccion_ruta.seccion
    avance = f"{seccion_ruta.porcentaje_final or 0:.0f} % · {'Completada' if seccion_ruta.estado == 'COMPLETADA' else 'En progreso'}"
    datos_seccion = [
        ("Asignatura", seccion.asignatura.nombre),
        ("NRC", seccion.nrc),
        ("Sección", seccion.seccion),
        ("Docente", ", ".join(f"{d.nombres} {d.apellidos}" for d in seccion.docentes.all())),
        ("Carrera", ", ".join(c.nombre for c in seccion.carreras.all())),
        ("Campus", f"{seccion.campus.nombre} ({seccion.campus.sede.nombre})"),
        ("Período", seccion.periodo.nombre),
        ("Avance de la Ruta", avance),
    ]

    grupos = []
    for equipo in (
        Equipo.objects.filter(seccion=seccion)
        .select_related("proyecto")
        .con_socio_vigente()
        .prefetch_related("integrantes")
        .order_by("numero_grupo")
    ):
        socio = equipo.socio_vigente
        vigentes = getattr(equipo, "participaciones_vigentes", [])
        participacion = vigentes[0] if vigentes else None
        grupos.append({
            "grupo": f"Grupo {equipo.numero_grupo}",
            "proyecto": equipo.proyecto.nombre if equipo.proyecto_id else "",
            "socio": socio.nombre_organizacion if socio else "Sin socio registrado",
            "integrantes": len(equipo.integrantes.all()),


            "contacto": _contacto(socio),
            "beneficiarios": participacion.beneficiarios_estimados if participacion else None,
            "servicio": (participacion.servicio_realizado or "") if participacion else "",
            "evaluacion": participacion.evaluacion if participacion else None,
            "comentario": (participacion.comentario or "") if participacion else "",
        })
    con_trabajo = any(g["beneficiarios"] is not None or g["servicio"] or g["evaluacion"] for g in grupos)

    actividades = actividades_de(seccion_ruta)
    etapas, _ = armar_etapas(actividades)
    avance_etapas = [
        {
            "etapa": f"{etapa['numero']}. {etapa['nombre']}",
            "hechas": f"{etapa['hechas']} de {etapa['total']}",
            "archivos": etapa["archivos"],
            "pendientes": [f"{a.ruta_actividad.orden}. {a.ruta_actividad.nombre}" for a in etapa["pendientes"]],
        }
        for etapa in etapas
    ]



    formularios = []
    for respuesta in (
        RespuestaFormulario.objects
        .filter(seccion=seccion, version__plantilla__codigo__in=set(FORMULARIO_POR_ORDEN.values()))
        .select_related("version__plantilla", "equipo")
        .order_by("fecha_envio", "id")
    ):
        formularios.append({
            "titulo": respuesta.version.plantilla.titulo,
            "grupo": f"Grupo {respuesta.equipo.numero_grupo}" if respuesta.equipo_id else "",
            "fecha": timezone.localtime(respuesta.fecha_envio),
            "filas": con_porcentaje_reprobacion(
                [(pregunta.texto, texto) for pregunta, texto in resumen_respuesta(respuesta) if texto]
            ),
        })

    encuestas = [
        (f"Encuesta {nombre}", RespuestaFormulario.objects.filter(seccion=seccion, version__plantilla__codigo=codigo).count())
        for codigo, nombre in ENCUESTAS.items()
    ]

    evidencias = [
        {
            "actividad": f"{actividad.ruta_actividad.orden}. {actividad.ruta_actividad.nombre}",
            "archivo": evidencia.archivo.nombre_original,
            "descripcion": evidencia.descripcion or "",
        }
        for actividad in actividades
        for evidencia in actividad.evidencias.all()
    ]

    return {
        "seccion": seccion,
        "datos_seccion": datos_seccion,
        "grupos": grupos,
        "con_trabajo": con_trabajo,
        "etapas": avance_etapas,
        "formularios": formularios,
        "encuestas": encuestas,
        "evidencias": evidencias,
    }


def generar_ficha_excel(seccion_ruta):
    """
    La ficha en Excel: una hoja por bloque y los formularios en una sola
    tabla (formulario, grupo, fecha, pregunta, respuesta) para filtrarla.
    """
    from core import excel

    datos = datos_ficha(seccion_ruta)
    seccion = datos["seccion"]
    libro, hoja = excel.nuevo_libro("Ficha", {
        "Documento": "Ficha del proyecto A+S",
        "Generado": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
    })
    hoja.append(["Dato", "Valor"])
    for dato, valor in datos["datos_seccion"]:
        hoja.append([dato, valor])
    excel.celda_texto(hoja.cell(hoja.max_row - 6, 2), seccion.nrc)

    formularios = libro.create_sheet("Formularios")
    formularios.append(["Formulario", "Grupo", "Fecha", "Pregunta", "Respuesta"])
    for formulario in datos["formularios"]:
        for pregunta, texto in formulario["filas"]:
            formularios.append([formulario["titulo"], formulario["grupo"], formulario["fecha"].replace(tzinfo=None), pregunta, texto])

    grupos = libro.create_sheet("Grupos")
    grupos.append([
        "Grupo", "Proyecto", "Socio comunitario", "Contacto", "Integrantes",
        "Beneficiarios", "Servicio realizado", "Evaluación (1 a 5)", "Comentario",
    ])
    for grupo in datos["grupos"]:
        grupos.append([
            grupo["grupo"], grupo["proyecto"], grupo["socio"], grupo["contacto"], grupo["integrantes"],
            grupo["beneficiarios"], grupo["servicio"], grupo["evaluacion"], grupo["comentario"],
        ])

    avance = libro.create_sheet("Avance por etapa")
    avance.append(["Etapa", "Hechas", "Archivos", "Pendientes"])
    for etapa in datos["etapas"]:
        avance.append([etapa["etapa"], etapa["hechas"], etapa["archivos"], "; ".join(etapa["pendientes"]) or "Nada pendiente"])
    avance.append([])
    avance.append(["Encuesta de satisfacción", "Respuestas"])
    for nombre, total in datos["encuestas"]:
        avance.append([nombre, total])

    evidencias = libro.create_sheet("Evidencias")
    evidencias.append(["Actividad", "Archivo", "Descripción"])
    for evidencia in datos["evidencias"]:
        evidencias.append([evidencia["actividad"], evidencia["archivo"], evidencia["descripcion"]])
    return libro


def generar_ficha_pdf(seccion_ruta):
    """Bytes del PDF de la ficha del proyecto de la sección (va en el ZIP)."""
    datos = datos_ficha(seccion_ruta)
    seccion = datos["seccion"]
    e = _estilos()
    ancho = A4[0] - 3.6 * cm
    historia = [
        Paragraph("Ficha del proyecto A+S", e["titulo"]),
        _p(f"{seccion.asignatura.nombre} · NRC {seccion.nrc} · Sección {seccion.seccion}", e["sub"]),
        Paragraph("Datos de la sección", e["h2"]),
        _tabla([list(fila) for fila in datos["datos_seccion"]], [4.2 * cm, ancho - 4.2 * cm], e, encabezado=False),
        Paragraph("Grupos", e["h2"]),
    ]
    if datos["grupos"]:
        filas = [["Grupo", "Proyecto", "Socio comunitario", "Integrantes"]]
        filas += [[g["grupo"], g["proyecto"], g["socio"], str(g["integrantes"])] for g in datos["grupos"]]
        historia.append(_tabla(filas, [2 * cm, 5.6 * cm, 6 * cm, ancho - 13.6 * cm], e))
    else:
        historia.append(_p("Aún no hay grupos registrados.", e["nota"]))

    if datos["con_trabajo"]:
        historia.append(Paragraph("Trabajo con el socio (lo informan los grupos)", e["h2"]))
        filas = [["Grupo", "Socio y contacto", "Benef.", "Servicio realizado", "Eval.", "Comentario"]]
        filas += [
            [
                g["grupo"], " · ".join(p for p in (g["socio"], g["contacto"]) if p),
                "" if g["beneficiarios"] is None else str(g["beneficiarios"]),
                g["servicio"], "" if g["evaluacion"] is None else f"{g['evaluacion']} / 5", g["comentario"],
            ]
            for g in datos["grupos"]
        ]
        historia.append(_tabla(filas, [1.7 * cm, 4.3 * cm, 1.4 * cm, 4.6 * cm, 1.3 * cm, ancho - 13.3 * cm], e))

    historia.append(Paragraph("Avance por etapa", e["h2"]))
    filas = [["Etapa", "Hechas", "Archivos", "Pendientes"]]
    filas += [
        [etapa["etapa"], etapa["hechas"], str(etapa["archivos"]), "\n".join(etapa["pendientes"]) or "Nada pendiente"]
        for etapa in datos["etapas"]
    ]
    historia.append(_tabla(filas, [5 * cm, 2 * cm, 2 * cm, ancho - 9 * cm], e))

    historia.append(Paragraph("Formularios llenados", e["h2"]))
    if not datos["formularios"]:
        historia.append(_p("Todavía no se ha llenado ningún formulario desde la Ruta.", e["nota"]))
    for formulario in datos["formularios"]:
        titulo = formulario["titulo"] + (f" · {formulario['grupo']}" if formulario["grupo"] else "")
        historia.append(_p(f"{titulo} ({formulario['fecha'].strftime('%d/%m/%Y')})", e["h3"]))
        if formulario["filas"]:
            historia.append(_tabla([list(f) for f in formulario["filas"]], [6.5 * cm, ancho - 6.5 * cm], e, encabezado=False))

    historia.append(Paragraph("Encuestas de satisfacción", e["h2"]))
    historia.append(_tabla(
        [["Encuesta", "Respuestas"]] + [[nombre, str(total)] for nombre, total in datos["encuestas"]],
        [8 * cm, 3 * cm], e,
    ))

    historia.append(Paragraph("Evidencias", e["h2"]))
    if datos["evidencias"]:
        filas = [["Actividad", "Archivo", "Descripción"]]
        filas += [[ev["actividad"], ev["archivo"], ev["descripcion"]] for ev in datos["evidencias"]]
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
