"""
Reportes en Excel del apartado Reportes (HU-08, RF-IND-04).

El cliente pidió (reunión del 2/11/2026) que todos los reportes queden en
este apartado. Cada reporte usa los mismos filtros combinables del panel de
indicadores y deja anotados en el archivo los filtros aplicados.
"""

from collections import defaultdict

from django.db.models import F, Prefetch
from django.utils import timezone

from academico.models import SeccionDocente
from core import excel, indicadores
from socios.centros_sercotec import normalizar_centro
from socios.models import ContactoSocio


SIN_CENTRO = "Sin centro SERCOTEC"


def leer_filtros(get):
    """Los filtros del panel, pero sin partir en el período vigente: un reporte parte con todo."""
    datos = get.copy()
    datos[indicadores.MARCA_FILTRADO] = "1"
    return indicadores.leer_filtros(datos)


def metadatos(filtros, reporte):
    return {
        "Reporte": reporte,
        "Generado": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
        "Filtros aplicados": ", ".join(c["etiqueta"] for c in indicadores.chips(filtros))
        or "Todos los años, sedes y carreras",
    }


def _participaciones(filtros):
    return (
        indicadores.participaciones_filtradas(filtros)
        .select_related(
            "socio__comuna", "socio__clasificacion", "sede", "campus__sede", "periodo",
            "carrera__facultad", "asignatura", "seccion", "equipo",
        )
        .prefetch_related(
            Prefetch(
                "seccion__seccion_docentes",
                queryset=SeccionDocente.objects.select_related("docente"),
            ),
            Prefetch(
                "socio__contactos",
                queryset=ContactoSocio.objects.order_by("-es_principal", "id"),
            ),
        )
        .order_by(
            F("periodo__anio").desc(nulls_last=True), F("fecha_inicio").desc(nulls_last=True),
            "socio__nombre_organizacion", "id",
        )
    )


def _anio(participacion):
    if participacion.periodo_id:
        return participacion.periodo.anio
    return participacion.fecha_inicio.year if participacion.fecha_inicio else None


def _docentes(participacion):
    if not participacion.seccion_id:
        return ""
    return ", ".join(str(sd.docente) for sd in participacion.seccion.seccion_docentes.all())


def _contacto(socio):
    contactos = list(socio.contactos.all())
    return contactos[0] if contactos else None


def _centro(socio):
    return normalizar_centro(socio.centro_servicio) or socio.centro_servicio or SIN_CENTRO


def _escribir_fila(hoja, valores, columnas_texto=()):
    """Agrega una fila; las columnas indicadas (1 = primera) quedan como texto (RUT, teléfono)."""
    fila = hoja.max_row + 1
    hoja.append(valores)
    for columna in columnas_texto:
        excel.celda_texto(hoja.cell(fila, columna), valores[columna - 1])


def libro_participaciones(filtros):
    """
    Una fila por participación de un socio: qué asignatura, carrera, docente,
    año y socio. Responde pedidos como "proyectos 2024 con docentes y socios".
    """
    datos = metadatos(filtros, "Proyectos y participaciones A+S")
    libro, hoja = excel.nuevo_libro("Participaciones", datos)
    hoja.append([
        "Año", "Período", "Origen", "Sede", "Campus", "Facultad", "Carrera", "Asignatura",
        "NRC", "Docente(s)", "Equipo", "Socio comunitario", "RUT socio", "Clasificación",
        "Comuna", "Centro SERCOTEC", "Servicio realizado", "Beneficiarios", "Evaluación",
        "Fecha inicio", "Fecha fin",
    ])
    for p in _participaciones(filtros):
        socio = p.socio
        sede = p.sede or (p.campus.sede if p.campus_id else None)
        _escribir_fila(hoja, [
            _anio(p),
            p.periodo.nombre if p.periodo_id else "",
            p.get_origen_display(),
            str(sede) if sede else "",
            p.campus.nombre if p.campus_id else "",
            str(p.carrera.facultad) if p.carrera_id and p.carrera.facultad_id else "",
            p.carrera.nombre if p.carrera_id else "",
            p.asignatura.nombre if p.asignatura_id else "",
            p.seccion.nrc if p.seccion_id else "",
            _docentes(p),
            f"Grupo {p.equipo.numero_grupo}" if p.equipo_id else "",
            socio.nombre_organizacion,
            socio.rut or "",
            str(socio.clasificacion) if socio.clasificacion_id else (socio.clasificacion_otra or ""),
            str(socio.comuna) if socio.comuna_id else "",
            _centro(socio),
            p.servicio_realizado or "",
            p.beneficiarios_estimados,
            p.evaluacion,
            p.fecha_inicio,
            p.fecha_fin,
        ], columnas_texto=(9, 13))
    return libro


def libro_centros_sercotec(filtros):
    """
    Emprendedores con los que realmente se trabajó (tienen una participación,
    es decir, el docente los eligió), agrupados por Centro de Negocios SERCOTEC
    y año. Es lo que el cliente necesita entregar a SERCOTEC para su estudio de
    seguimiento (reunión del 2/11/2026).
    """
    datos = metadatos(filtros, "Emprendedores por Centro de Negocios SERCOTEC")
    libro, resumen = excel.nuevo_libro("Resumen por centro", datos)

    # (centro, año) -> {socio_id: (socio, participaciones de ese año)}
    grupos = defaultdict(dict)
    for p in _participaciones(filtros):
        clave = (_centro(p.socio), _anio(p))
        socio, lista = grupos[clave].setdefault(p.socio_id, (p.socio, []))
        lista.append(p)

    def orden(clave):
        centro, anio = clave
        return (centro == SIN_CENTRO, centro, -(anio or 0))

    resumen.append(["Centro SERCOTEC", "Año", "Emprendedores", "Participaciones"])
    for clave in sorted(grupos, key=orden):
        socios = grupos[clave]
        resumen.append([clave[0], clave[1], len(socios), sum(len(lista) for _, lista in socios.values())])

    detalle = libro.create_sheet("Emprendedores")
    excel.agregar_metadatos(detalle, datos)
    detalle.append([
        "Centro SERCOTEC", "Año", "Emprendedor / organización", "RUT", "Comuna", "Contacto",
        "Correo", "Teléfono", "Carrera(s)", "Asignatura(s)", "Docente(s)", "Participaciones",
    ])
    for clave in sorted(grupos, key=orden):
        centro, anio = clave
        for socio, lista in sorted(grupos[clave].values(), key=lambda par: par[0].nombre_organizacion.lower()):
            contacto = _contacto(socio)
            _escribir_fila(detalle, [
                centro,
                anio,
                socio.nombre_organizacion,
                socio.rut or "",
                str(socio.comuna) if socio.comuna_id else "",
                contacto.nombre if contacto else "",
                (contacto.correo or "") if contacto else "",
                (contacto.telefono or "") if contacto else "",
                ", ".join(sorted({p.carrera.nombre for p in lista if p.carrera_id})),
                ", ".join(sorted({p.asignatura.nombre for p in lista if p.asignatura_id})),
                ", ".join(sorted({d for p in lista for d in _docentes(p).split(", ") if d})),
                len(lista),
            ], columnas_texto=(4, 8))
    return libro
