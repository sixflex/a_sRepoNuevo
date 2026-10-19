"""
Indicadores del panel del coordinador (HU-08, RF-IND-01 a RF-IND-03, RF-RUT-05).

Todo se calcula sobre los datos ya modelados: secciones y sus carreras y
docentes (academico), equipos e integrantes (proyectos), participaciones de
socios (socios), Rutas A+S (rutas) y respuestas de las encuestas de
evaluación (encuestas). No guarda nada: solo consulta.
"""

from collections import defaultdict
from urllib.parse import urlencode

from django.db.models import Avg, Count, Q, Sum
from django.urls import reverse

from academico.models import (
    Asignatura,
    Campus,
    Carrera,
    Facultad,
    PeriodoAcademico,
    Seccion,
    SeccionCarrera,
    SeccionDocente,
    Sede,
)
from proyectos.models import IntegranteEquipo
from rutas.models import SeccionRuta
from rutas.services import con_avance, porcentaje_avance
from socios.models import Comuna, ParticipacionSocio


# Parámetros GET del panel de filtros, en el orden en que se muestran los chips.
FILTROS = ["sede", "campus", "anio", "periodo", "facultad", "carrera", "asignatura", "comuna"]

# Filtros del mapa del portal público (RF-PUB-01): sin período ni asignatura.
FILTROS_PUBLICOS = ["sede", "anio", "carrera", "comuna"]

# Marca que indica que el usuario ya eligió filtros (aunque los haya quitado
# todos): sin ella el panel parte en el período vigente.
MARCA_FILTRADO = "f"

# Semáforo del avance de la Ruta (texto además del color, por accesibilidad).
UMBRAL_MEDIO = 40
UMBRAL_ALTO = 80

# Encuestas de evaluación A+S (códigos fijos: la Ruta de Cielo depende de ellos).
ENCUESTAS_SATISFACCION = [
    ("EVALUACION_AS_ESTUDIANTES", "Estudiantes"),
    ("EVALUACION_AS_DOCENTES", "Docentes"),
    ("EVALUACION_AS_SOCIOS", "Socios comunitarios"),
]

# Dimensiones de las encuestas (configuracion_json["dimension"] de cada fila
# de las cuadrículas 1 a 5), en el orden de la tabla de promedios.
DIMENSIONES = [
    ("aprendizaje", "Aprendizaje"),
    ("reflexion", "Reflexión"),
    ("servicio", "Servicio"),
    ("socio_comunitario", "Socio comunitario"),
    ("universidad", "Relación con la Universidad"),
]

# Respuestas que cuentan como satisfechas en la valoración general.
SATISFECHO_DESDE = 4

# El ítem de perfil de egreso está en la valoración general de estudiantes y
# docentes. El cliente dijo que ese dato "no le dice nada" en el dashboard de
# Talca; por ahora se incluye, y basta con poner False para excluirlo.
INCLUIR_PERFIL_EGRESO = True


def _entero(valor):
    valor = (valor or "").strip()
    return int(valor) if valor.isdigit() else None


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

def leer_filtros(get):
    """
    Filtros elegidos (ids enteros o None). La primera vez, sin parámetros,
    parte en el período vigente, como se ve el inicio hoy.
    """
    filtros = {nombre: _entero(get.get(nombre)) for nombre in FILTROS}
    filtrado = MARCA_FILTRADO in get or any(filtros.values())

    if not filtrado:
        vigente = (
            PeriodoAcademico.objects
            .filter(estado="Activo")
            .order_by("-anio", "-id")
            .first()
        )
        if vigente:
            filtros["periodo"] = vigente.id

    filtros["comparar"] = get.get("comparar", "1" if not filtrado else "") == "1"
    return filtros


def filtros_publicos(get):
    """Filtros del mapa público: parte con todos los años (sin período vigente)."""
    filtros = {nombre: None for nombre in FILTROS}
    for nombre in FILTROS_PUBLICOS:
        filtros[nombre] = _entero(get.get(nombre))
    return filtros


def opciones_publicas():
    """Listas de los filtros públicos: solo valores que tienen participaciones."""
    participaciones = ParticipacionSocio.objects.all()
    return {
        "sedes": Sede.objects.filter(
            Q(participaciones_socios__in=participaciones)
            | Q(campus__participaciones_socios__in=participaciones)
        ).distinct().order_by("nombre"),
        "anios": sorted(_anios_con_datos(), reverse=True),
        "carreras": Carrera.objects.filter(participaciones_socios__in=participaciones).distinct().order_by("nombre"),
        "comunas": Comuna.objects.filter(socios__participaciones__in=participaciones).distinct().order_by("nombre"),
    }


def _url(filtros, quitar=None):
    datos = {MARCA_FILTRADO: "1"}
    for nombre in FILTROS:
        if nombre != quitar and filtros.get(nombre):
            datos[nombre] = filtros[nombre]
    if filtros.get("comparar"):
        datos["comparar"] = "1"
    return "?" + urlencode(datos)


def chips(filtros):
    """Filtros aplicados como chips, cada uno con la URL que lo quita."""
    modelos = {
        "sede": Sede, "campus": Campus, "periodo": PeriodoAcademico,
        "facultad": Facultad, "carrera": Carrera, "asignatura": Asignatura,
        "comuna": Comuna,
    }
    resultado = []
    for nombre in FILTROS:
        valor = filtros.get(nombre)
        if not valor:
            continue
        if nombre == "anio":
            etiqueta = str(valor)
        else:
            objeto = modelos[nombre].objects.filter(pk=valor).first()
            if not objeto:
                continue
            etiqueta = getattr(objeto, "nombre", str(objeto))
        resultado.append({"etiqueta": etiqueta, "url": _url(filtros, quitar=nombre)})
    return resultado


def opciones_filtros():
    """Listas del panel de filtros."""
    return {
        "sedes": Sede.objects.order_by("nombre"),
        "campus": Campus.objects.select_related("sede").order_by("sede__nombre", "nombre"),
        "anios": (
            PeriodoAcademico.objects.order_by("-anio")
            .values_list("anio", flat=True).distinct()
        ),
        "periodos": PeriodoAcademico.objects.order_by("-anio", "-id"),
        "facultades": Facultad.objects.order_by("nombre"),
        "carreras": Carrera.objects.select_related("facultad").order_by("nombre"),
        "asignaturas": Asignatura.objects.order_by("nombre"),
        "comunas": (
            Comuna.objects
            .filter(socios__isnull=False)
            .distinct()
            .order_by("nombre")
        ),
    }


def _secciones(filtros, periodo=None, anio=None):
    """Secciones A+S que cumplen los filtros (las declaradas "no A+S" quedan fuera)."""
    secciones = Seccion.objects.exclude(seccion_carreras__declaracion_as=False)
    periodo = periodo if periodo is not None else filtros.get("periodo")
    anio = anio if anio is not None else filtros.get("anio")

    if periodo:
        secciones = secciones.filter(periodo_id=periodo)
    if anio:
        secciones = secciones.filter(periodo__anio=anio)
    if filtros.get("sede"):
        secciones = secciones.filter(campus__sede_id=filtros["sede"])
    if filtros.get("campus"):
        secciones = secciones.filter(campus_id=filtros["campus"])
    if filtros.get("facultad"):
        secciones = secciones.filter(seccion_carreras__carrera__facultad_id=filtros["facultad"])
    if filtros.get("carrera"):
        secciones = secciones.filter(seccion_carreras__carrera_id=filtros["carrera"])
    if filtros.get("asignatura"):
        secciones = secciones.filter(asignatura_id=filtros["asignatura"])
    if filtros.get("comuna"):
        secciones = secciones.filter(
            participaciones_socios__socio__comuna_id=filtros["comuna"],
        )
    return secciones.distinct()


def _participaciones(filtros, periodo=None, anio=None):
    """
    Participaciones de socios con los filtros. Se filtra por el contexto de la
    propia participación, así también cuentan las históricas sin equipo
    (RF-MIG-02).
    """
    participaciones = ParticipacionSocio.objects.all()
    periodo = periodo if periodo is not None else filtros.get("periodo")
    anio = anio if anio is not None else filtros.get("anio")

    if periodo:
        participaciones = participaciones.filter(periodo_id=periodo)
    if anio:
        participaciones = participaciones.filter(
            Q(periodo__anio=anio) | Q(periodo__isnull=True, fecha_inicio__year=anio)
        )
    if filtros.get("sede"):
        participaciones = participaciones.filter(
            Q(sede_id=filtros["sede"]) | Q(campus__sede_id=filtros["sede"])
        )
    if filtros.get("campus"):
        participaciones = participaciones.filter(campus_id=filtros["campus"])
    if filtros.get("facultad"):
        participaciones = participaciones.filter(carrera__facultad_id=filtros["facultad"])
    if filtros.get("carrera"):
        participaciones = participaciones.filter(carrera_id=filtros["carrera"])
    if filtros.get("asignatura"):
        participaciones = participaciones.filter(asignatura_id=filtros["asignatura"])
    if filtros.get("comuna"):
        participaciones = participaciones.filter(socio__comuna_id=filtros["comuna"])
    return participaciones


# ---------------------------------------------------------------------------
# Tarjetas
# ---------------------------------------------------------------------------

def _valores(filtros, periodo=None, anio=None):
    secciones = _secciones(filtros, periodo, anio)
    seccion_carreras = SeccionCarrera.objects.filter(seccion__in=secciones)
    if filtros.get("facultad"):
        seccion_carreras = seccion_carreras.filter(carrera__facultad_id=filtros["facultad"])
    if filtros.get("carrera"):
        seccion_carreras = seccion_carreras.filter(carrera_id=filtros["carrera"])

    estudiantes = IntegranteEquipo.objects.filter(equipo__seccion__in=secciones).count()
    estudiantes_planificados = False
    if not estudiantes:
        estudiantes = seccion_carreras.aggregate(
            total=Sum("estudiantes_planificados"),
        )["total"] or 0
        estudiantes_planificados = bool(estudiantes)

    participaciones = _participaciones(filtros, periodo, anio)

    return {
        "asignaturas": secciones.values("asignatura").distinct().count(),
        "docentes": (
            SeccionDocente.objects.filter(seccion__in=secciones)
            .values("docente").distinct().count()
        ),
        "carreras": seccion_carreras.values("carrera").distinct().count(),
        "estudiantes": estudiantes,
        "estudiantes_planificados": estudiantes_planificados,
        "socios": participaciones.values("socio").distinct().count(),
        "participaciones": participaciones.count(),
    }


def estudiantes_participantes(filtros):
    return _valores(filtros)["estudiantes"]


def _periodo_anterior(periodo_id):
    """El período que viene justo antes (por año, fecha de inicio e id)."""
    periodos = list(
        PeriodoAcademico.objects.order_by("anio", "fecha_inicio", "id")
        .values_list("id", "anio")
    )
    ids = [id_ for id_, _ in periodos]
    if periodo_id not in ids or ids.index(periodo_id) == 0:
        return None
    return PeriodoAcademico.objects.get(pk=ids[ids.index(periodo_id) - 1])


def _variacion(actual, anterior):
    diferencia = actual - anterior
    if diferencia > 0:
        return f"+{diferencia} vs período anterior"
    if diferencia < 0:
        return f"−{abs(diferencia)} vs período anterior"
    return "igual que el período anterior"


def tarjetas(filtros):
    """Las 5 tarjetas del período, con su variación si se pidió comparar."""
    actual = _valores(filtros)
    anterior = None

    if filtros.get("comparar"):
        if filtros.get("periodo"):
            previo = _periodo_anterior(filtros["periodo"])
            if previo:
                anterior = _valores(filtros, periodo=previo.id, anio=previo.anio)
        elif filtros.get("anio"):
            anterior = _valores(filtros, anio=filtros["anio"] - 1)

    def tarjeta(clave, etiqueta, detalle=None):
        variacion = _variacion(actual[clave], anterior[clave]) if anterior else None
        return {
            "etiqueta": etiqueta,
            "valor": actual[clave],
            "detalle": detalle or variacion,
        }

    socios = tarjeta(
        "socios", "Socios comunitarios",
        f"organizaciones únicas · {actual['participaciones']} "
        f"participaci{'ón' if actual['participaciones'] == 1 else 'ones'}",
    )
    estudiantes = tarjeta("estudiantes", "Estudiantes participantes")
    if actual["estudiantes_planificados"]:
        estudiantes["detalle"] = "planificados (aún sin equipos registrados)"

    return [
        tarjeta("asignaturas", "Asignaturas A+S"),
        tarjeta("docentes", "Docentes participantes"),
        tarjeta("carreras", "Carreras participantes"),
        estudiantes,
        socios,
    ]


# ---------------------------------------------------------------------------
# Avance de la Ruta A+S por carrera (RF-RUT-03, RF-RUT-05)
# ---------------------------------------------------------------------------

def nivel_avance(porcentaje):
    if porcentaje >= UMBRAL_ALTO:
        return {"clave": "alto", "texto": "Alto"}
    if porcentaje >= UMBRAL_MEDIO:
        return {"clave": "medio", "texto": "Medio"}
    return {"clave": "bajo", "texto": "Bajo"}


def avance_por_carrera(filtros):
    """
    Promedio del avance de las Rutas de cada carrera, de menor a mayor, con el
    detalle por docente. El coordinador solo monitorea (RF-RUT-05 CA1).
    """
    rutas = (
        con_avance(
            SeccionRuta.objects.filter(seccion__in=_secciones(filtros))
            .select_related("seccion", "seccion__asignatura")
        )
        .prefetch_related(
            "seccion__docentes",
            "seccion__seccion_carreras__carrera",
        )
    )

    por_carrera = defaultdict(list)
    for ruta in rutas:
        porcentaje = porcentaje_avance(ruta.completadas_obligatorias, ruta.total_obligatorias)
        docentes = ", ".join(
            f"{docente.nombres} {docente.apellidos}" for docente in ruta.seccion.docentes.all()
        ) or "Sin docente asignado"
        detalle = {
            "docente": docentes,
            "seccion": f"{ruta.seccion.asignatura.nombre} · Sección {ruta.seccion.seccion}",
            "porcentaje": porcentaje,
            "nivel": nivel_avance(porcentaje),
            "pendientes": ruta.total_obligatorias - ruta.completadas_obligatorias,
            "cerrada": ruta.estado == "COMPLETADA",
        }
        for seccion_carrera in ruta.seccion.seccion_carreras.all():
            carrera = seccion_carrera.carrera
            if filtros.get("carrera") and carrera.id != filtros["carrera"]:
                continue
            if filtros.get("facultad") and carrera.facultad_id != filtros["facultad"]:
                continue
            por_carrera[carrera].append(detalle)

    resultado = []
    for carrera, detalles in por_carrera.items():
        porcentaje = round(sum(d["porcentaje"] for d in detalles) / len(detalles))
        resultado.append({
            "carrera": carrera.nombre,
            "porcentaje": porcentaje,
            "nivel": nivel_avance(porcentaje),
            "docentes": sorted(detalles, key=lambda d: d["porcentaje"]),
        })
    return sorted(resultado, key=lambda c: (c["porcentaje"], c["carrera"]))


# ---------------------------------------------------------------------------
# Satisfacción (encuestas de evaluación A+S)
# ---------------------------------------------------------------------------

def _respuestas_escala(codigo, filtros):
    from encuestas.models import RespuestaPregunta

    respuestas = RespuestaPregunta.objects.filter(
        respuesta__version__plantilla__codigo=codigo,
        pregunta__tipo="ESCALA",
        valor_escala__isnull=False,
    )
    periodo = PeriodoAcademico.objects.filter(pk=filtros.get("periodo")).first()
    anio = filtros.get("anio") or (periodo.anio if periodo else None)

    if periodo:
        # Las respuestas por enlace público no siempre traen el período: se
        # ubican por su fecha (las fechas del período, o al menos su año).
        if periodo.fecha_inicio and periodo.fecha_fin:
            por_fecha = Q(
                respuesta__fecha_envio__date__range=(periodo.fecha_inicio, periodo.fecha_fin),
            )
        else:
            por_fecha = Q(respuesta__fecha_envio__year=periodo.anio)
        respuestas = respuestas.filter(
            Q(respuesta__periodo=periodo) | (Q(respuesta__periodo__isnull=True) & por_fecha)
        )
    elif anio:
        respuestas = respuestas.filter(
            Q(respuesta__periodo__anio=anio)
            | Q(respuesta__periodo__isnull=True, respuesta__fecha_envio__year=anio)
        )
    if filtros.get("sede"):
        respuestas = respuestas.filter(
            Q(respuesta__sede_id=filtros["sede"]) | Q(respuesta__campus__sede_id=filtros["sede"])
        )
    if filtros.get("campus"):
        respuestas = respuestas.filter(respuesta__campus_id=filtros["campus"])
    if filtros.get("facultad"):
        respuestas = respuestas.filter(respuesta__carrera__facultad_id=filtros["facultad"])
    if filtros.get("carrera"):
        respuestas = respuestas.filter(respuesta__carrera_id=filtros["carrera"])
    if filtros.get("asignatura"):
        respuestas = respuestas.filter(respuesta__asignatura_id=filtros["asignatura"])
    return respuestas


def satisfaccion(filtros):
    """
    Anillos: % de respuestas 4 o 5 en la valoración general de cada encuesta
    (estudiantes P19, docentes P18, socios P12), con su n. Tabla: promedio
    1 a 5 por dimensión. Sin respuestas, el anillo queda vacío (no 0%).
    """
    anillos = []
    promedios = {clave: {} for clave, _ in DIMENSIONES}

    for codigo, publico in ENCUESTAS_SATISFACCION:
        respuestas = _respuestas_escala(codigo, filtros)

        generales = respuestas.filter(pregunta__configuracion_json__valoracion_general=True)
        if not INCLUIR_PERFIL_EGRESO:
            generales = generales.exclude(pregunta__configuracion_json__perfil_egreso=True)
        total = generales.count()
        satisfechas = generales.filter(valor_escala__gte=SATISFECHO_DESDE).count()
        personas = generales.values("respuesta").distinct().count()
        numero_pregunta = (
            generales.values_list("pregunta__configuracion_json__numero", flat=True).first()
        )
        porcentaje = round(satisfechas * 100 / total, 1) if total else None
        anillos.append({
            "publico": publico,
            "porcentaje": porcentaje,
            "personas": personas,
            "pregunta": numero_pregunta,
        })

        por_dimension = (
            respuestas.exclude(pregunta__configuracion_json__dimension=None)
            .values("pregunta__configuracion_json__dimension")
            .annotate(promedio=Avg("valor_escala"), cantidad=Count("id"))
        )
        for fila in por_dimension:
            clave = fila["pregunta__configuracion_json__dimension"]
            if clave in promedios:
                promedios[clave][codigo] = round(float(fila["promedio"]), 1)

    tabla = []
    for clave, etiqueta in DIMENSIONES:
        tabla.append({
            "dimension": etiqueta,
            "valores": [
                promedios[clave].get(codigo) for codigo, _ in ENCUESTAS_SATISFACCION
            ],
        })
    return {
        "anillos": anillos,
        "tabla": tabla,
        "publicos": [publico for _, publico in ENCUESTAS_SATISFACCION],
        "hay_datos": any(anillo["porcentaje"] is not None for anillo in anillos),
    }


# ---------------------------------------------------------------------------
# Mapa territorial (RF-IND-03): agregado por comuna, sin direcciones
# ---------------------------------------------------------------------------

def mapa(filtros, detalle=False):
    """
    Puntos por comuna (centro de la comuna, nunca la dirección), con totales.

    Con detalle=True (solo el mapa del coordinador, que requiere sesión) cada
    punto incluye además sus socios con dirección exacta y contacto principal;
    las intervenciones se revisan en el historial del socio. El portal público lo llama sin detalle (RF-IND-03 CA1).
    """
    participaciones = (
        _participaciones(filtros)
        .filter(socio__comuna__lat_centro__isnull=False, socio__comuna__lon_centro__isnull=False)
        .select_related("socio__comuna", "carrera", "periodo")
    )
    if detalle:
        participaciones = participaciones.prefetch_related("socio__contactos")

    comunas = {}
    for participacion in participaciones:
        comuna = participacion.socio.comuna
        datos = comunas.setdefault(comuna.id, {
            "comuna": comuna.nombre,
            "lat": float(comuna.lat_centro),
            "lon": float(comuna.lon_centro),
            "socios": set(),
            "proyectos": set(),
            "carreras": set(),
            "anios": set(),
            "detalle": {},
        })
        datos["socios"].add(participacion.socio_id)
        if participacion.proyecto_id:
            datos["proyectos"].add(participacion.proyecto_id)
        elif participacion.equipo_id:
            datos["proyectos"].add(f"equipo-{participacion.equipo_id}")
        if participacion.carrera:
            datos["carreras"].add(participacion.carrera.nombre)
        anio = _anio_participacion(participacion)
        if anio:
            datos["anios"].add(anio)
        if detalle:
            _agregar_detalle(datos["detalle"], participacion.socio)

    puntos = []
    for datos in comunas.values():
        punto = {
            "comuna": datos["comuna"],
            "lat": datos["lat"],
            "lon": datos["lon"],
            "socios": len(datos["socios"]),
            "proyectos": len(datos["proyectos"]),
            "carreras": sorted(datos["carreras"]),
            "anios": sorted(datos["anios"]),
        }
        if detalle:
            punto["detalle"] = sorted(datos["detalle"].values(), key=lambda s: s["nombre"].lower())
        puntos.append(punto)

    return {
        "puntos": puntos,
        "top_proyectos": sorted(puntos, key=lambda p: -p["proyectos"])[:5],
        "top_socios": sorted(puntos, key=lambda p: -p["socios"])[:5],
        "total_socios": len({socio for datos in comunas.values() for socio in datos["socios"]}),
        "total_proyectos": sum(p["proyectos"] for p in puntos),
    }


def _anio_participacion(participacion):
    if participacion.periodo:
        return participacion.periodo.anio
    if participacion.fecha_inicio:
        return participacion.fecha_inicio.year
    return None


def _agregar_detalle(socios, socio):
    """Datos del socio para el mapa del coordinador (el detalle está en su historial)."""
    if socio.id in socios:
        return
    contactos = list(socio.contactos.all())
    contacto = next((c for c in contactos if c.es_principal), contactos[0] if contactos else None)
    socios[socio.id] = {
        "nombre": socio.nombre_organizacion,
        "direccion": socio.direccion_exacta or "",
        "contacto": contacto.nombre if contacto else "",
        "telefono": (contacto.telefono or "") if contacto else "",
        "correo": (contacto.correo or "") if contacto else "",
        "url": reverse("socios:detalle_historial", args=[socio.id]),
    }


# ---------------------------------------------------------------------------
# Evolución por año
# ---------------------------------------------------------------------------

EVOLUCION_INDICADORES = [
    ("asignaturas", "Asignaturas"),
    ("docentes", "Docentes"),
    ("carreras", "Carreras"),
    ("estudiantes", "Estudiantes"),
    ("socios", "Socios"),
]


def _anios_con_datos():
    """Años de los períodos más los de participaciones históricas sin período."""
    return (
        set(PeriodoAcademico.objects.values_list("anio", flat=True))
        | {
            anio for anio in ParticipacionSocio.objects
            .filter(periodo__isnull=True, fecha_inicio__isnull=False)
            .values_list("fecha_inicio__year", flat=True)
        }
    )


def evolucion(filtros):
    """Indicadores por año con los demás filtros (el año y el período no aplican)."""
    sin_periodo = {**filtros, "periodo": None, "anio": None}
    anios = sorted(_anios_con_datos())[-6:]

    series = {clave: [] for clave, _ in EVOLUCION_INDICADORES}
    for anio in anios:
        valores = _valores(sin_periodo, anio=anio)
        for clave, _ in EVOLUCION_INDICADORES:
            series[clave].append(valores[clave])

    indicadores = []
    for clave, etiqueta in EVOLUCION_INDICADORES:
        maximo = max(series[clave], default=0) or 1
        indicadores.append({
            "clave": clave,
            "etiqueta": etiqueta,
            "barras": [
                {"anio": anio, "valor": valor, "alto": round(valor * 100 / maximo)}
                for anio, valor in zip(anios, series[clave])
            ],
        })
    return indicadores
