from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.ordenamiento import OPCIONES_ORDEN, orden_pedido, ordenar_por_fecha
from rutas.services import obtener_recordatorios_ruta
from usuarios.permissions import es_coordinador, es_docente
from usuarios.decorators import coordinador_only_required, coordinador_required, docente_required
from usuarios.services import aviso_vincular_cuenta

from academico.models import (PeriodoAcademico, Seccion)

from publico.models import Noticia

# Formulario unificado de los centros de negocio (Investigación de Mercados,
# Consultoría Empresas, Gestión de Procesos): la convocatoria a emprendedores.
CODIGO_CONVOCATORIA_CENTROS = "FICHA_EMPRENDEDORES"


def _enlace_convocatoria_centros():
    """Enlace público abierto de la Ficha de emprendedores, o None si no está publicada."""
    from django.urls import reverse

    from encuestas.models import FormularioPlantilla
    from rutas.services import enlaces_abiertos_por_plantilla

    plantilla = FormularioPlantilla.objects.filter(codigo=CODIGO_CONVOCATORIA_CENTROS, activo=True).first()
    if plantilla is None:
        return None
    enlace = enlaces_abiertos_por_plantilla([plantilla.id]).get(plantilla.id)
    return reverse("encuestas:responder", args=[enlace.token]) if enlace else None


def inicio(request):
    if request.user.is_authenticated:
        if es_coordinador(request.user):
            return redirect("core:coordinacion")
        if es_docente(request.user):
            return redirect("core:inicio_docente")

    from publico.portal import configuracion_portal

    from . import indicadores

    # Qué eligió mostrar el Coordinador (RF-PUB-01); lo apagado ni se calcula.
    portal = configuracion_portal()
    filtros = indicadores.filtros_publicos(request.GET)

    mapa = None
    if portal["mapa"]["activo"]:
        mapa = indicadores.mapa_publico(filtros, campos=portal["mapa"]["opciones"])

    catalogo = indicadores.catalogo_publico(filtros) if portal["catalogo"]["activo"] else []
    cifras = None
    if portal["cifras"]["activo"] or portal["mapa"]["activo"]:
        cifras = indicadores.cifras_publicas(filtros)

    noticias = []
    if portal["noticias"]["activo"]:
        noticias = Noticia.objects.filter(estado="PUBLICADA").order_by("-fecha_publicacion")[:3]

    return render(request, "core/inicio.html", {
        "convocatoria_centros": _enlace_convocatoria_centros(),
        "portal": portal,
        "filtros": filtros,
        "hay_filtros": any(filtros.get(nombre) for nombre in indicadores.FILTROS_PUBLICOS),
        "opciones": indicadores.opciones_publicas(),
        "mapa": mapa,
        "cifras": cifras,
        "catalogo": catalogo,
        "catalogo_anios": sorted({p["anio"] for p in catalogo if p["anio"]}, reverse=True),
        "noticias": noticias,
    })


@coordinador_required
def panel_coordinacion(request):
    """
    Inicio del coordinador: lo que pasa en el período vigente y lo que hay que
    atender (cartas, pendientes, indicadores, mapa y avance de la Ruta), con un
    selector de sede. El análisis con todos los filtros, la satisfacción, la
    evolución y la exportación a Excel están en el Panel de indicadores
    (RF-IND-01, RF-IND-04). Los cálculos están en core/indicadores.py.
    """
    from cartas.models import SolicitudCarta
    from planificacion.models import Planificacion
    from socios.models import PostulacionSocio

    from . import indicadores

    from academico.models import Sede

    filtros = indicadores.filtros_inicio(request.GET)
    periodo_actual = PeriodoAcademico.objects.filter(pk=filtros["periodo"]).first()
    sedes = Sede.objects.order_by("nombre")
    sede_actual = sedes.filter(pk=filtros["sede"]).first() if filtros["sede"] else None
    avance_carreras = indicadores.avance_por_carrera(filtros)
    cartas_pendientes = SolicitudCarta.objects.filter(
        estado="PENDIENTE"
    ).order_by("fecha_solicitud", "id")

    cantidad_cartas_pendientes = cartas_pendientes.count()
    carta_mas_antigua = cartas_pendientes.first()

    antiguedad_maxima_dias = 0

    if carta_mas_antigua:
        antiguedad_maxima_dias = max(
            0,
            (timezone.localdate() - timezone.localtime(
                carta_mas_antigua.fecha_solicitud
            ).date()).days
        )

    if antiguedad_maxima_dias >= 7:
        nivel_alerta_cartas = "alta"
    elif antiguedad_maxima_dias >= 3:
        nivel_alerta_cartas = "media"
    else:
        nivel_alerta_cartas = "baja"
    pendientes = [
        {
            "label": "Cartas por revisar",
            "value": cantidad_cartas_pendientes,
            "icon": "bi-envelope-paper",
            "url": reverse("cartas:listar_solicitudes_coordinacion"),
            "antiguedad_dias": antiguedad_maxima_dias,
            "solicitud_mas_antigua_id": (
                carta_mas_antigua.id if carta_mas_antigua else None
            ),
            "nivel_alerta": nivel_alerta_cartas,
        },
        {
            "label": "Planificaciones con filas observadas",
            "value": Planificacion.objects.filter(filas_observadas__gt=0).count(),
            "icon": "bi-exclamation-triangle",
            "url": reverse("core:planificacion_coordinacion"),
        },
        {
            "label": "Postulaciones de socios por revisar",
            "value": PostulacionSocio.objects.filter(estado="RECIBIDA").count(),
            "icon": "bi-person-plus",
            "url": reverse("socios:lista_postulaciones"),
        },
        {
            "label": f"Docentes con Ruta bajo {indicadores.UMBRAL_MEDIO} %",
            "value": indicadores.rutas_bajo_umbral(avance_carreras),
            "icon": "bi-hourglass-split",
            "url": "#avance-titulo",
        },
    ]

    # El mapa del coordinador sí trae dirección, contacto e intervenciones de cada socio.
    mapa = indicadores.mapa(filtros, detalle=True)

    return render(
        request,
        "core/coordinacion.html",
        {
            "filtros": filtros,
            "periodo_actual": periodo_actual,
            "sedes": sedes,
            "sede_actual": sede_actual,
            "tarjetas": indicadores.tarjetas(filtros),
            "avance_carreras": avance_carreras,
            "umbrales": {"medio": indicadores.UMBRAL_MEDIO, "alto": indicadores.UMBRAL_ALTO},
            "pendientes": pendientes,
            "mapa": mapa,
            "aviso_vincular": aviso_vincular_cuenta(request),
        },
    )


@coordinador_only_required
def exportar_indicadores(request):
    from auditoria.services import registrar_auditoria
    from . import excel, indicadores

    filtros = indicadores.leer_filtros(request.GET)
    filtros_legibles = indicadores.chips(filtros)
    metadatos = {
        "Generado": timezone.localtime().strftime("%d/%m/%Y %H:%M"),
        "Filtros aplicados": ", ".join(c["etiqueta"] for c in filtros_legibles)
        or "Todos los períodos, sedes y carreras",
    }
    libro, hoja = excel.nuevo_libro("Resumen", metadatos)
    hoja.append(["Indicador", "Valor", "Detalle"])
    for tarjeta in indicadores.tarjetas(filtros):
        hoja.append([tarjeta["etiqueta"], tarjeta["valor"], tarjeta["detalle"] or ""])

    avance = libro.create_sheet("Avance por carrera")
    excel.agregar_metadatos(avance, metadatos)
    avance.append(["Carrera", "Porcentaje", "Nivel", "Docente", "Sección", "Pendientes"])
    for carrera in indicadores.avance_por_carrera(filtros):
        for docente in carrera["docentes"]:
            avance.append([
                carrera["carrera"], carrera["porcentaje"], carrera["nivel"]["texto"],
                docente["docente"], docente["seccion"], docente["pendientes"],
            ])

    satisfaccion = libro.create_sheet("Satisfacción")
    excel.agregar_metadatos(satisfaccion, metadatos)
    satisfaccion.append(["Público", "Porcentaje 4 y 5", "Personas", "Pregunta"])
    datos_satisfaccion = indicadores.satisfaccion(filtros)
    for fila in datos_satisfaccion["anillos"]:
        satisfaccion.append([fila["publico"], fila["porcentaje"], fila["personas"], fila["pregunta"]])
    satisfaccion.append([])
    satisfaccion.append(["Público", "Ítem", "Porcentaje 4 y 5", "Respuestas"])
    for fila in datos_satisfaccion["anillos"]:
        for pregunta in fila["preguntas"]:
            satisfaccion.append([fila["publico"], pregunta["texto"], pregunta["porcentaje"], pregunta["respuestas"]])

    evolucion = libro.create_sheet("Evolución")
    excel.agregar_metadatos(evolucion, metadatos)
    evolucion.append(["Indicador", "Año", "Valor"])
    for serie in indicadores.evolucion(filtros):
        for barra in serie["barras"]:
            evolucion.append([serie["etiqueta"], barra["anio"], barra["valor"]])

    mapa = libro.create_sheet("Mapa territorial")
    excel.agregar_metadatos(mapa, metadatos)
    mapa.append(["Comuna", "Latitud", "Longitud", "Socios", "Proyectos", "Carreras", "Años", "Teléfono"])
    for punto in indicadores.mapa(filtros, detalle=True)["puntos"]:
        detalles = punto.get("detalle") or [{}]
        for detalle in detalles:
            fila = mapa.max_row + 1
            mapa.append([
                punto["comuna"], punto["lat"], punto["lon"], punto["socios"],
                punto["proyectos"], ", ".join(punto["carreras"]),
                ", ".join(str(anio) for anio in punto["anios"]), "",
            ])
            excel.celda_texto(mapa.cell(fila, 8), detalle.get("telefono", ""))

    registrar_auditoria(
        request=request, entidad="Indicadores", entidad_id="panel",
        accion="EXPORTAR_INDICADORES", valores_nuevos={"filtros": filtros},
    )
    return excel.respuesta_excel(libro, "indicadores.xlsx")


@coordinador_required
def planificacion_coordinacion(request):
    from planificacion.models import Planificacion

    planificaciones = (
        Planificacion.objects
        .select_related(
            "enlace",
            "enlace__campus",
            "enlace__campus__sede",
            "enlace__periodo",
            "enlace__unidad_academica",
            "enlace__unidad_academica__facultad",
            "enlace__unidad_academica__carrera",
        )
        .prefetch_related(
            "filas__docentes",
            "filas__errores",
        )
    )
    orden = orden_pedido(request)
    planificaciones = ordenar_por_fecha(planificaciones, "fecha_envio_final", orden)

    return render(
        request,
        "core/planificacion_coordinacion.html",
        {
            "planificaciones": planificaciones,
            "orden": orden,
            "opciones_orden": OPCIONES_ORDEN,
        },
    )



@docente_required
def panel_docente(request):
    secciones_docente = (
        Seccion.objects
        .filter(docentes__usuario=request.user)
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .distinct()
    )

    periodos = (
        PeriodoAcademico.objects
        .filter(secciones__in=secciones_docente)
        .distinct()
        .order_by("-anio", "-id")
    )

    anios = (
        periodos
        .order_by("-anio")
        .values_list("anio", flat=True)
        .distinct()
    )

    anio_seleccionado = request.GET.get("anio", "").strip()
    periodo_seleccionado = request.GET.get("periodo", "").strip()

    secciones = secciones_docente

    if anio_seleccionado:
        if anio_seleccionado.isdigit():
            secciones = secciones.filter(
                periodo__anio=int(anio_seleccionado)
            )
        else:
            secciones = secciones.none()

    if periodo_seleccionado:
        if periodo_seleccionado.isdigit():
            secciones = secciones.filter(
                periodo_id=int(periodo_seleccionado)
            )
        else:
            secciones = secciones.none()

    if anio_seleccionado:
        periodos = periodos.filter(
            anio=anio_seleccionado
        ) if anio_seleccionado.isdigit() else periodos.none()

    secciones = secciones.order_by(
        "-periodo__anio",
        "-periodo_id",
        "asignatura__nombre",
        "asignatura_id",
        "seccion",
    )

    secciones = list(secciones)

    recordatorios = obtener_recordatorios_ruta(secciones)
    for seccion in secciones:
        seccion.recordatorio_ruta = recordatorios.get(seccion.id)

    # Una tarjeta por asignatura y período, con sus secciones adentro.
    grupos = []
    for seccion in secciones:
        clave = (seccion.periodo_id, seccion.asignatura_id)
        if not grupos or grupos[-1]["clave"] != clave:
            grupos.append({
                "clave": clave,
                "asignatura": seccion.asignatura,
                "periodo": seccion.periodo,
                "secciones": [],
            })
        grupos[-1]["secciones"].append(seccion)

    return render(
        request,
        "core/docente.html",
        {
            "secciones": secciones,
            "grupos": grupos,
            "anios": anios,
            "periodos": periodos,
            "anio_seleccionado": anio_seleccionado,
            "periodo_id": periodo_seleccionado,
            "periodo_seleccionado": periodo_seleccionado,
            "filtros_activos": bool(
                anio_seleccionado or periodo_seleccionado
            ),
        },
    )


@docente_required
def inicio_docente(request):
    from django.db.models import Prefetch

    from rutas.models import SeccionActividad, SeccionRuta
    from rutas.services import (
        con_avance,
        es_actividad_cierre,
        recordatorios_cierre,
    )

    secciones = (
        Seccion.objects
        .filter(docentes__usuario=request.user)
        .distinct()
    )

    rutas = list(
        con_avance(
            SeccionRuta.objects
            .filter(seccion__in=secciones)
            .select_related(
                "seccion",
                "seccion__asignatura",
                "seccion__periodo",
            )
            .prefetch_related(
                Prefetch(
                    "actividades",
                    queryset=(
                        SeccionActividad.objects
                        .filter(completada_por_docente__isnull=True)
                        .select_related("ruta_actividad")
                        .order_by("ruta_actividad__orden")
                    ),
                    to_attr="actividades_pendientes",
                ),
                "invitaciones_cierre__socio",
            )
        )
        .order_by(
            "-seccion__periodo__anio",
            "seccion__asignatura__nombre",
        )
    )

    total_pendientes = 0

    for ruta in rutas:
        # Recordatorio visible en el panel, sin correo programado (RF-RUT-04).
        ruta.recordatorios = []

        if ruta.estado != "COMPLETADA":
            for actividad in ruta.actividades_pendientes:
                nombre = actividad.ruta_actividad.nombre

                if (
                    es_actividad_cierre(actividad.ruta_actividad)
                    and not ruta.invitaciones_cierre.all()
                ):
                    nombre += ": indica si habrá cierre e invita al Socio"

                if not actividad.ruta_actividad.es_obligatoria:
                    nombre += " (opcional)"

                ruta.recordatorios.append(nombre)

            ruta.recordatorios += recordatorios_cierre(ruta)

        ruta.pendientes_obligatorias = (
            ruta.total_obligatorias
            - ruta.completadas_obligatorias
        )

        ruta.avance_calculado = (
            round(
                ruta.completadas_obligatorias
                * 100
                / ruta.total_obligatorias
            )
            if ruta.total_obligatorias
            else 0
        )

        total_pendientes += ruta.pendientes_obligatorias

    from cartas.services import avisos_cartas_docente

    # Rutas agrupadas por asignatura (y período), como en Mis secciones:
    # dos secciones del mismo ramo se ven juntas con su avance promedio.
    from core.indicadores import nivel_avance

    grupos_rutas = []
    por_clave = {}
    for ruta in sorted(rutas, key=lambda r: (
        -(r.seccion.periodo.anio if r.seccion.periodo_id else 0),
        -(r.seccion.periodo_id or 0),
        r.seccion.asignatura.nombre,
        r.seccion.seccion or "",
    )):
        clave = (ruta.seccion.periodo_id, ruta.seccion.asignatura_id)
        if clave not in por_clave:
            por_clave[clave] = {
                "asignatura": ruta.seccion.asignatura,
                "periodo": ruta.seccion.periodo,
                "rutas": [],
            }
            grupos_rutas.append(por_clave[clave])
        ruta.nivel = nivel_avance(ruta.avance_calculado)
        por_clave[clave]["rutas"].append(ruta)
    for grupo in grupos_rutas:
        grupo["porcentaje"] = round(
            sum(r.avance_calculado for r in grupo["rutas"]) / len(grupo["rutas"])
        )
        grupo["nivel"] = nivel_avance(grupo["porcentaje"])
        grupo["pendientes"] = sum(r.pendientes_obligatorias for r in grupo["rutas"])
        grupo["completadas"] = sum(r.estado == "COMPLETADA" for r in grupo["rutas"])

    # Promedio de sus Rutas (pedido del cliente): cada sección pesa lo mismo.
    # Se mide en el período vigente para que las Rutas de semestres ya
    # cerrados no inflen el número; si no tiene Rutas en él, usa todas.
    from rutas.services import promedio_rutas

    vigente = PeriodoAcademico.objects.filter(estado="Activo").order_by("-anio", "-id").first()
    rutas_promedio = [ruta for ruta in rutas if vigente and ruta.seccion.periodo_id == vigente.id] or rutas
    promedio = promedio_rutas(rutas_promedio)
    periodo_promedio = vigente if vigente and rutas_promedio is not rutas else None

    return render(
        request,
        "core/inicio_docente.html",
        {
            "total_secciones": secciones.count(),
            "rutas_completadas": sum(
                ruta.estado == "COMPLETADA"
                for ruta in rutas
            ),
            "total_pendientes": total_pendientes,
            "promedio_rutas": promedio,
            "rutas_en_promedio": len(rutas_promedio),
            "periodo_promedio": periodo_promedio,
            "rutas": rutas,
            "grupos_rutas": grupos_rutas,
            "avisos": avisos_cartas_docente(request.user),
            "aviso_vincular": aviso_vincular_cuenta(request),
        },
    )

@login_required
def detalle_seccion(request, seccion_id):
    """
    Ficha única de la sección para ambos roles. El docente ve sus
    herramientas (registro de equipos, equipos y Ruta); el coordinador ve
    además los docentes y consulta equipos y Ruta en modo lectura, sin
    botones que lo lleven a páginas exclusivas del docente.
    """
    seccion = get_object_or_404(
        Seccion.objects
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .prefetch_related(
            "docentes",
            "seccion_carreras__carrera__facultad",
            "seccion_docentes__docente",
        ),
        id=seccion_id,
    )

    vista_coordinador = es_coordinador(request.user)

    if vista_coordinador:
        pass

    elif es_docente(request.user):
        pertenece_al_docente = seccion.docentes.filter(
            usuario=request.user
        ).exists()

        if not pertenece_al_docente:
            raise PermissionDenied

    else:
        raise PermissionDenied

    equipos = None

    if vista_coordinador:
        equipos = (
            seccion.equipos
            .con_socio_vigente()
            .prefetch_related("integrantes")
            .order_by("numero_grupo")
        )

    socios_elegidos = None
    if not vista_coordinador:
        from socios.services import socios_elegidos_seccion
        socios_elegidos = list(socios_elegidos_seccion(seccion))

    return render(
        request,
        "core/detalle_seccion.html",
        {
            "seccion": seccion,
            "vista_coordinador": vista_coordinador,
            "equipos": equipos,
            "socios_elegidos": socios_elegidos,
        },
    )


def _planificacion_coordinacion(planificacion_id):
    from planificacion.models import Planificacion

    return get_object_or_404(
        Planificacion.objects
        .select_related(
            "enlace",
            "enlace__campus",
            "enlace__campus__sede",
            "enlace__periodo",
            "enlace__unidad_academica",
            "enlace__unidad_academica__facultad",
            "enlace__unidad_academica__carrera",
        ),
        id=planificacion_id,
    )


@coordinador_required
def detalle_planificacion_coordinacion(
    request,
    planificacion_id,
):
    from planificacion import services as servicios_planificacion

    planificacion = _planificacion_coordinacion(planificacion_id)

    filas = (
        planificacion.filas.all()
        .select_related("carrera_resuelta", "seccion_resultante")
        .prefetch_related("docentes", "errores")
        .order_by("numero_fila", "id")
    )
    por_revisar = planificacion.estado == servicios_planificacion.PLAN_ENVIADA
    filas_revision = [
        (fila, servicios_planificacion.revision_fila(fila) if por_revisar else None)
        for fila in filas
    ]

    return render(
        request,
        "core/detalle_planificacion_coordinacion.html",
        {
            "planificacion": planificacion,
            "filas": filas,
            "filas_revision": filas_revision,
            "por_revisar": por_revisar,
            "motivo_devolucion": (
                servicios_planificacion.motivo_devolucion(planificacion)
                if planificacion.estado == servicios_planificacion.PLAN_DEVUELTA
                else ""
            ),
            "PLAN_ENVIADA": servicios_planificacion.PLAN_ENVIADA,
            "PLAN_APROBADA": servicios_planificacion.PLAN_APROBADA,
            "PLAN_DEVUELTA": servicios_planificacion.PLAN_DEVUELTA,
        },
    )


@coordinador_required
def aprobar_planificacion_coordinacion(request, planificacion_id):
    """Botón general «Aprobar»: crea lo nuevo y las secciones (HU-01)."""
    from django.contrib import messages

    from planificacion.services import PlanificacionNoAprobable, aprobar_planificacion

    planificacion = _planificacion_coordinacion(planificacion_id)
    if request.method != "POST":
        return redirect("core:detalle_planificacion_coordinacion", planificacion_id)

    try:
        secciones, creados = aprobar_planificacion(planificacion, request=request)
    except PlanificacionNoAprobable as error:
        messages.error(request, str(error))
    else:
        detalle = [f"{secciones} sección(es) incorporada(s)"]
        if creados["asignaturas"]:
            detalle.append(f"{len(creados['asignaturas'])} asignatura(s) nueva(s)")
        if creados["docentes"]:
            detalle.append(f"{len(creados['docentes'])} docente(s) nuevo(s)")
        messages.success(request, "Planificación aprobada: " + ", ".join(detalle) + ".")
    return redirect("core:detalle_planificacion_coordinacion", planificacion_id)


@coordinador_required
def devolver_planificacion_coordinacion(request, planificacion_id):
    """Devuelve la planificación a Dirección con un motivo y le avisa por correo."""
    from django.contrib import messages

    from planificacion.email_service import enviar_correo_devolucion
    from planificacion.services import PlanificacionNoAprobable, devolver_planificacion

    planificacion = _planificacion_coordinacion(planificacion_id)
    if request.method != "POST":
        return redirect("core:detalle_planificacion_coordinacion", planificacion_id)

    motivo = (request.POST.get("motivo") or "").strip()
    if not motivo:
        messages.error(request, "Escriba el motivo para que Dirección sepa qué corregir.")
        return redirect("core:detalle_planificacion_coordinacion", planificacion_id)

    try:
        devolver_planificacion(planificacion, motivo, request=request)
    except PlanificacionNoAprobable as error:
        messages.error(request, str(error))
        return redirect("core:detalle_planificacion_coordinacion", planificacion_id)

    try:
        enviar_correo_devolucion(request, planificacion.enlace, motivo)
    except Exception:
        messages.warning(
            request,
            "La planificación quedó devuelta y el enlace abierto, pero no se pudo enviar el correo. "
            f"Avise a {planificacion.enlace.destinatario_correo} o reenvíe el enlace.",
        )
    else:
        messages.success(
            request,
            f"Planificación devuelta. Se avisó por correo a {planificacion.enlace.destinatario_correo}.",
        )
    return redirect("core:detalle_planificacion_coordinacion", planificacion_id)


@coordinador_required
def editar_fila_planificacion_coordinacion(request, planificacion_id, fila_id):
    """
    El Coordinador corrige a mano una fila recibida (asignatura, docentes,
    horario...) antes de aprobar. Al guardar se vuelve a revisar la fila.
    """
    from django.contrib import messages
    from django.db import transaction

    from auditoria.services import registrar_auditoria
    from planificacion import services as servicios_planificacion
    from planificacion.forms import DocenteFilaFormSet, FilaPlanificacionForm
    from planificacion.views import _docente_tiene_datos, _docentes_initial, _guardar_docentes

    planificacion = _planificacion_coordinacion(planificacion_id)
    fila = get_object_or_404(planificacion.filas, pk=fila_id)
    url_detalle = reverse("core:detalle_planificacion_coordinacion", args=[planificacion.id])

    if planificacion.estado != servicios_planificacion.PLAN_ENVIADA or fila.seccion_resultante_id:
        messages.info(request, "Solo se pueden editar filas de una planificación por revisar que aún no se incorporan.")
        return redirect(url_detalle)

    from planificacion.forms import opciones_planificacion

    facultad = servicios_planificacion.facultad_de_enlace(planificacion.enlace)
    opciones = opciones_planificacion(facultad, planificacion.enlace.campus)

    def foto():
        return {
            **{
                campo: getattr(fila, campo)
                for campo in FilaPlanificacionForm.Meta.fields
            },
            "docentes": [
                {"rut": d.rut, "nombre": d.nombre, "correo": d.correo, "telefono": d.telefono}
                for d in fila.docentes.order_by("id")
            ],
        }

    if request.method == "POST":
        form = FilaPlanificacionForm(request.POST, instance=fila, opciones=opciones)
        docentes = DocenteFilaFormSet(request.POST, prefix="docentes")
        docentes_validos = docentes.is_valid()
        if docentes_validos and not any(
            _docente_tiene_datos(getattr(f, "cleaned_data", {})) for f in docentes.forms
        ):
            docentes._non_form_errors = docentes.error_class(["Debe dejar al menos un docente."])
            docentes_validos = False

        if form.is_valid() and docentes_validos:
            anteriores = foto()
            with transaction.atomic():
                form.save()
                _guardar_docentes(fila, docentes)
                servicios_planificacion.validar_fila(fila)
                servicios_planificacion.actualizar_totales(planificacion)
                registrar_auditoria(
                    request=request,
                    entidad="FilaPlanificacion",
                    entidad_id=fila.id,
                    accion="EDITAR_FILA_PLANIFICACION",
                    valores_anteriores=anteriores,
                    valores_nuevos=foto(),
                )
            if fila.estado_validacion == servicios_planificacion.ESTADO_OBSERVADA:
                messages.warning(request, f"Fila {fila.numero_fila} guardada, pero sigue con observaciones.")
            else:
                messages.success(request, f"Fila {fila.numero_fila} corregida y lista para aprobar.")
            return redirect(f"{url_detalle}#fila-{fila.id}")
    else:
        form = FilaPlanificacionForm(instance=fila, opciones=opciones)
        docentes = DocenteFilaFormSet(prefix="docentes", initial=_docentes_initial(fila))
        if not docentes.initial:
            docentes.extra = 1

    revision = servicios_planificacion.revision_fila(fila)
    return render(
        request,
        "core/editar_fila_planificacion.html",
        {
            "planificacion": planificacion,
            "fila": fila,
            "form": form,
            "docentes": docentes,
            "revision": revision,
            "errores": fila.errores.all(),
            "asignaturas_por_carrera": servicios_planificacion.opciones_asignaturas(),
            "facultad_fija": facultad.nombre if facultad else "",
        },
    )


@coordinador_required
def panel_indicadores_coordinacion(request):
    from . import indicadores
    filtros = indicadores.leer_filtros(request.GET)

    contexto = {
        "filtros": filtros,
        "chips": indicadores.chips(filtros),
        "opciones": indicadores.opciones_filtros(),
        "tarjetas": indicadores.tarjetas(filtros),
        "evolucion": indicadores.evolucion(filtros),
        "avance_carreras": indicadores.avance_por_carrera(filtros),
        "umbrales": {"medio": indicadores.UMBRAL_MEDIO, "alto": indicadores.UMBRAL_ALTO},
        "satisfaccion": indicadores.satisfaccion(filtros),
    }

    return render(request, "core/indicadores_coordinacion.html", contexto)
