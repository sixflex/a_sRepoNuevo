"""
Catálogo de proyectos A+S del Coordinador (menú "Proyectos").

Un proyecto es la participación de un socio comunitario con un equipo o una
sección (ParticipacionSocio, la fuente única de la relación socio-proyecto),
incluidas las históricas cargadas desde los Excel del cliente (RF-MIG-02).
Se separan en "En curso" y "Cerrados":

- Cerrado: viene del histórico, la participación ya terminó (fecha_fin), su
  período ya terminó, o el docente completó la Ruta de la sección.
- En curso: todo lo demás, es decir, lo que se está haciendo este semestre.

Es una vista interna: muestra el nombre del socio (el Coordinador puede
verlo). El portal público usa core.indicadores.catalogo_publico, sin nombres.
"""

from django.db.models import Q
from django.utils import timezone

from socios.models import ParticipacionSocio

EN_CURSO = "en_curso"
CERRADOS = "cerrados"


def _cerrado(hoy):
    return (
        Q(origen="HISTORICO")
        | Q(fecha_fin__lte=hoy)
        | Q(periodo__fecha_fin__lt=hoy)
        | Q(seccion__ruta_asignada__estado="COMPLETADA")
    )


def _entero(valor):
    valor = (valor or "").strip()
    return int(valor) if valor.isdigit() else None


def leer_filtros(get):
    return {
        "estado": CERRADOS if get.get("estado") == CERRADOS else EN_CURSO,
        "anio": _entero(get.get("anio")),
        "sede": _entero(get.get("sede")),
        "carrera": _entero(get.get("carrera")),
        "q": (get.get("q") or "").strip()[:100],
    }


def _filtrar(participaciones, filtros):
    if filtros["anio"]:
        participaciones = participaciones.filter(
            Q(periodo__anio=filtros["anio"]) | Q(periodo__isnull=True, fecha_inicio__year=filtros["anio"])
        )
    if filtros["sede"]:
        participaciones = participaciones.filter(
            Q(sede_id=filtros["sede"]) | Q(campus__sede_id=filtros["sede"])
        )
    if filtros["carrera"]:
        participaciones = participaciones.filter(carrera_id=filtros["carrera"])
    if filtros["q"]:
        q = filtros["q"]
        participaciones = participaciones.filter(
            Q(servicio_realizado__icontains=q)
            | Q(socio__nombre_organizacion__icontains=q)
            | Q(asignatura__nombre__icontains=q)
            | Q(seccion__nrc__icontains=q)
        )
    return participaciones


def proyectos(filtros, hoy=None):
    """
    (lista de la pestaña elegida, {"en_curso": n, "cerrados": n}). Los
    contadores respetan los demás filtros, así se ve cuántos hay en la otra
    pestaña.
    """
    hoy = hoy or timezone.localdate()
    base = _filtrar(ParticipacionSocio.objects.all(), filtros)
    cerrado = _cerrado(hoy)
    en_curso = base.exclude(cerrado)
    cerrados = base.filter(cerrado)

    elegidos = (cerrados if filtros["estado"] == CERRADOS else en_curso).select_related(
        "socio__comuna", "periodo", "carrera", "asignatura", "sede", "campus__sede",
        "seccion__ruta_asignada", "equipo",
    ).prefetch_related("seccion__seccion_docentes__docente").order_by(
        "-periodo__anio", "-fecha_inicio", "carrera__nombre", "asignatura__nombre", "id",
    ).distinct()

    return elegidos, {EN_CURSO: en_curso.distinct().count(), CERRADOS: cerrados.distinct().count()}


def tarjeta(participacion):
    """Datos de una tarjeta del catálogo."""
    seccion = participacion.seccion
    ruta = getattr(seccion, "ruta_asignada", None) if seccion else None
    servicio = " ".join((participacion.servicio_realizado or "").split())
    sede = participacion.sede or (participacion.campus.sede if participacion.campus else None)
    docentes = []
    if seccion:
        docentes = [
            f"{sd.docente.nombres} {sd.docente.apellidos}".strip()
            for sd in seccion.seccion_docentes.all()
        ]
    return {
        "id": participacion.id,
        "servicio": servicio[:1].upper() + servicio[1:] if servicio else "",
        "socio": participacion.socio.nombre_organizacion,
        "socio_id": participacion.socio_id,
        "comuna": participacion.socio.comuna.nombre if participacion.socio.comuna else "",
        "carrera": participacion.carrera.nombre if participacion.carrera else "",
        "asignatura": participacion.asignatura.nombre if participacion.asignatura else "",
        "nrc": seccion.nrc if seccion else "",
        "grupo": participacion.equipo.numero_grupo if participacion.equipo else None,
        "periodo": str(participacion.periodo) if participacion.periodo else (
            str(participacion.fecha_inicio.year) if participacion.fecha_inicio else ""
        ),
        "sede": sede.nombre if sede else "",
        "docentes": docentes,
        "beneficiarios": participacion.beneficiarios_estimados,
        "historico": participacion.origen == "HISTORICO",
        "ruta": ruta,
    }
