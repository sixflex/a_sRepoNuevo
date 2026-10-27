from django.contrib import messages
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from academico.models import Asignatura, Campus, Carrera, PeriodoAcademico, Sede
from usuarios.decorators import coordinador_required, docente_required
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST
from proyectos.models import Equipo
from rutas.models import SeccionActividad
from rutas.services import url_recurso
from auditoria.services import registrar_auditoria

from django.core.exceptions import ValidationError
from encuestas import services as encuestas_services
from encuestas.models import EnlaceFormulario, FormularioVersion, RespuestaFormulario
from .models import Convocatoria, PostulacionSocio, SocioComunitario, ContactoSocio, Comuna, ClasificacionSocio
from core.ordenamiento import OPCIONES_ORDEN, ORDEN_NOMBRE, orden_pedido, ordenar_por_fecha

from . import services
from .forms import DECISION_HABILITAR, SocioPropuestoForm
from .constantes import ESTADOS_POSTULACION, ESTADOS_SOCIO_SELECCIONABLES, estados_siguientes, etiqueta
from .services import enviar_notificacion_postulacion
from .validators import validar_rut_chileno

from .models import (ClasificacionSocio,Comuna,ParticipacionSocio,PostulacionSocio,SocioComunitario,)

ESTADOS_SOCIO = [codigo for codigo, _ in services.ESTADOS_SOCIO]

# Largo máximo del motivo de cambio de socio (igual que gestionar_equipo).
MAX_LARGO_MOTIVO_CAMBIO_SOCIO = 255

# Estados en los que un socio puede ser elegido por un docente (CDE-60)
ESTADOS_SELECCIONABLES = ESTADOS_SOCIO_SELECCIONABLES


def socios_disponibles():
    """
    Socios disponibles para otros grupos: activos, no provisionales y en un
    estado seleccionable (CDE-65).
    """
    return SocioComunitario.objects.filter(
        activo=True,
        es_provisional=False,
        estado_revision__in=ESTADOS_SELECCIONABLES,
    )


def comunas_con_socios(socios):
    """
    Comunas donde hay socios del listado, para el filtro: una comuna nueva
    aparece sola en cuanto se registra un socio en ella.
    """
    return Comuna.objects.filter(socios__in=socios).distinct().order_by('nombre')


@docente_required
def catalogo_socios_docente(request):
    """
    Lista únicamente los Socios Comunitarios aprobados, disponibles o asignados, activos
    y no provisionales, que un docente puede seleccionar para sus asignaturas.
    Los socios conservados solo en historial no aparecen aquí.
    """
    socios = socios_disponibles().select_related('clasificacion', 'comuna')

    q = request.GET.get('q', '').strip()
    comuna_id = request.GET.get('comuna')
    clasificacion_id = request.GET.get('clasificacion')
    estado = request.GET.get('estado', '')

    if q:
        # Nombre, RUT o lo que hace el socio (rubro, producto, servicio realizado).
        socios = socios.filter(
            Q(nombre_organizacion__icontains=q) |
            Q(rut__icontains=q) |
            services.filtro_que_hace(q)
        )
    if comuna_id:
        socios = socios.filter(comuna_id=comuna_id)
    if clasificacion_id:
        socios = socios.filter(clasificacion_id=clasificacion_id)
    if estado in ESTADOS_SELECCIONABLES:
        socios = socios.filter(estado_revision=estado)

    socios = list(socios)
    descripciones = services.descripciones_socios([s.id for s in socios])
    for socio in socios:
        socio.que_hace = descripciones.get(socio.id, "")

    context = {
        'socios': socios,
        'comunas': comunas_con_socios(socios_disponibles()),
        'clasificaciones': ClasificacionSocio.objects.filter(activo=True),
        'estados': ESTADOS_SELECCIONABLES,
        'q': q,
        'comuna_id': comuna_id,
        'clasificacion_id': clasificacion_id,
        'estado': estado,
    }
    return render(request, 'socios/catalogo_docente.html', context)


@coordinador_required
def lista_socios_coordinador(request):
    """
    Panel completo de búsqueda, filtros combinados y revisión para el Coordinador.
    """
    # Lo que falta revisar (postulaciones y socios propuestos por equipos, en
    # estado Recibido) y los postulantes rechazados se ven en Postulaciones;
    # el catálogo muestra los socios ya aceptados.
    catalogo = SocioComunitario.objects.exclude(estado_revision="RECIBIDO").exclude(
        Q(estado_revision="RECHAZADO")
        & Q(Exists(PostulacionSocio.objects.filter(socio=OuterRef('pk'))))
    )
    socios = catalogo.select_related('clasificacion', 'comuna')
    orden = orden_pedido(request, permitidos=(ORDEN_NOMBRE, 'recientes', 'antiguos'), por_defecto=ORDEN_NOMBRE)
    if orden == ORDEN_NOMBRE:
        socios = socios.order_by('nombre_organizacion', 'pk')
    else:
        socios = ordenar_por_fecha(socios, 'fecha_creacion', orden)

    # Parámetros de Búsqueda (CDE-62)
    q = request.GET.get('q', '').strip()
    clasificacion_id = request.GET.get('clasificacion')
    comuna_id = request.GET.get('comuna')

    # Parámetros de Filtros Combinados (CDE-63)
    estado = request.GET.get('estado')
    es_provisional = request.GET.get('provisional')
    sede_id = request.GET.get('sede')
    campus_id = request.GET.get('campus')
    carrera_id = request.GET.get('carrera')
    periodo_id = request.GET.get('periodo')
    anio = request.GET.get('anio')

    # Disponibilidad (CDE-65): 'disponibles' o 'historial'
    vista = request.GET.get('vista')

    if q:
        socios = socios.filter(
            Q(nombre_organizacion__icontains=q) |
            Q(rut__icontains=q) |
            Q(contactos__nombre__icontains=q)
        ).distinct()

    if clasificacion_id:
        socios = socios.filter(clasificacion_id=clasificacion_id)

    if comuna_id:
        socios = socios.filter(comuna_id=comuna_id)

    if estado:
        socios = socios.filter(estado_revision=estado)

    if es_provisional:
        socios = socios.filter(es_provisional=(es_provisional == '1'))

    if vista == 'disponibles':
        socios = socios.filter(
            activo=True,
            es_provisional=False,
            estado_revision__in=ESTADOS_SELECCIONABLES,
        )
    elif vista == 'historial':
        socios = socios.filter(
            Q(activo=False) | Q(estado_revision="TRABAJO_TERMINADO")
        )

    # Filtros por historial académico de participaciones (CDE-63)
    if sede_id:
        socios = socios.filter(participaciones__sede_id=sede_id).distinct()
    if campus_id:
        socios = socios.filter(participaciones__campus_id=campus_id).distinct()
    if carrera_id:
        socios = socios.filter(participaciones__carrera_id=carrera_id).distinct()
    if periodo_id:
        socios = socios.filter(participaciones__periodo_id=periodo_id).distinct()
    if anio:
        socios = socios.filter(participaciones__periodo__anio=anio).distinct()

    # Cada socio trae los estados a los que el coordinador puede moverlo.
    socios = list(socios)
    for socio in socios:
        socio.estados_siguientes = estados_siguientes(socio.estado_revision)

    # RF-IND-02: organizaciones únicas frente a participaciones registradas,
    # sobre los socios del resultado y el mismo contexto académico filtrado.
    participaciones_resultado = ParticipacionSocio.objects.filter(
        socio__in=[socio.pk for socio in socios]
    )
    for campo, valor in (
        ('sede_id', sede_id),
        ('campus_id', campus_id),
        ('carrera_id', carrera_id),
        ('periodo_id', periodo_id),
        ('periodo__anio', anio),
    ):
        if valor:
            participaciones_resultado = participaciones_resultado.filter(**{campo: valor})
    total_participaciones = participaciones_resultado.count()
    total_organizaciones_con_participacion = (
        participaciones_resultado.values('socio_id').distinct().count()
    )

    context = {
        'socios': socios,
        'clasificaciones': ClasificacionSocio.objects.filter(activo=True),
        'comunas': comunas_con_socios(catalogo),
        'sedes': Sede.objects.filter(activo=True),
        'campus_list': Campus.objects.filter(activo=True),
        'carreras': Carrera.objects.filter(activo=True),
        'periodos': PeriodoAcademico.objects.all(),
        'anios': PeriodoAcademico.objects.values_list('anio', flat=True).distinct().order_by('-anio'),
        'filtros': request.GET,
        'estados_socio': [e for e in services.ESTADOS_SOCIO if e[0] != 'RECIBIDO'],
        'total_participaciones': total_participaciones,
        'total_organizaciones_con_participacion': total_organizaciones_con_participacion,
        'orden': orden,
        'opciones_orden': [(ORDEN_NOMBRE, 'Nombre (A-Z)'), *OPCIONES_ORDEN],
    }
    return render(request, 'socios/lista_coordinador.html', context)


@coordinador_required
def cambiar_estado_socio(request, socio_id):
    """
    Permite al coordinador aprobar, rechazar o habilitar un socio (provisional o
    en revisión).
    """
    socio = get_object_or_404(SocioComunitario, pk=socio_id)

    if request.method == "POST":
        try:
            historial = services.cambiar_estado_socio(
                request,
                socio,
                request.POST.get("estado_revision"),
                es_provisional=request.POST.get("es_provisional") == "1",
                motivo=request.POST.get("motivo", ""),
            )
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            if historial:
                messages.success(
                    request,
                    f"El estado de {socio.nombre_organizacion} fue actualizado a "
                    f"«{etiqueta(services.ESTADOS_SOCIO, socio.estado_revision)}».",
                )
            else:
                messages.info(request, "No hubo cambios que guardar.")

    return redirect('socios:lista_coordinador')


@coordinador_required
def detalle_historial_socio(request, socio_id):
    """
    Muestra la ficha detallada del Socio Comunitario, el historial cronológico
    de sus participaciones.
    """
    socio = get_object_or_404(
        SocioComunitario.objects.select_related('clasificacion', 'comuna'),
        pk=socio_id
    )
    contactos = socio.contactos.filter(activo=True)

    participaciones = ParticipacionSocio.objects.filter(socio=socio).select_related(
        'equipo', 'proyecto', 'sede', 'campus', 'periodo', 'carrera', 'asignatura', 'seccion'
    ).order_by('-periodo__anio', '-fecha_inicio', '-pk')

    context = {
        'socio': socio,
        'contactos': contactos,
        'participaciones': participaciones,
        'historial_estados': services.historial_estados_socio(socio),
    }
    return render(request, 'socios/detalle_historial.html', context)


@coordinador_required
def lista_postulaciones(request):
    """
    Lo que el coordinador debe revisar, en tres pestañas: las postulaciones que
    llegan por el formulario de una convocatoria (RF-SC-01/02), los socios que
    propone un equipo al inscribirse (RF-SC-04) y los posibles socios que
    sugiere Dirección de Carrera en su planificación (RF-ACA-03), para
    invitarlos a postular.
    """
    origen = request.GET.get('origen')
    if origen not in ('equipos', 'direccion'):
        origen = 'convocatoria'
    orden = orden_pedido(request)

    postulaciones = ordenar_por_fecha(PostulacionSocio.objects.select_related(
        'convocatoria', 'socio__comuna', 'revisado_por_usuario'
    ), 'fecha_recepcion', orden)

    propuestos = list(ordenar_por_fecha(
        services.socios_propuestos_por_equipos()
        .prefetch_related(Prefetch(
            'participaciones',
            queryset=ParticipacionSocio.objects.filter(equipo__isnull=False)
            .select_related('equipo__seccion__asignatura').order_by('fecha_inicio', 'pk'),
            to_attr='participaciones_equipo',
        )),
        'fecha_creacion', orden,
    ))
    for socio in propuestos:
        socio.equipo_origen = (
            socio.participaciones_equipo[0].equipo if socio.participaciones_equipo else None
        )

    sugeridos = services.socios_sugeridos_por_direccion(orden)
    enlace_postulacion = request.build_absolute_uri(reverse('socios:postular_publico'))

    return render(request, 'socios/lista_postulaciones.html', {
        'origen': origen,
        'sugeridos': sugeridos,
        'sugeridos_sin_registrar': sum(1 for s in sugeridos if not s['socio_id']),
        'enlace_postulacion': enlace_postulacion,
        'asunto_invitacion': 'Invitación a postular como Socio Comunitario A+S',
        'cuerpo_invitacion': (
            'Hola, Dirección de Carrera sugirió a su organización para trabajar con estudiantes '
            f'en asignaturas A+S. Puede postular en este enlace: {enlace_postulacion}'
        ),
        'postulaciones': postulaciones,
        'pendientes_convocatoria': sum(1 for p in postulaciones if p.estado == 'RECIBIDA'),
        'propuestos': propuestos,
        'orden': orden,
        'opciones_orden': OPCIONES_ORDEN,
    })


@coordinador_required
def revisar_socio_propuesto(request, socio_id):
    """
    El coordinador corrige los datos del socio que propuso un equipo y decide
    si queda disponible para otros grupos o solo en el historial del equipo
    (RF-SC-04 CA2, RN-10).
    """
    socio = get_object_or_404(
        SocioComunitario.objects.select_related('clasificacion', 'comuna'), pk=socio_id,
    )
    if socio.postulaciones.exists():
        # Los que postularon por una convocatoria se revisan en su postulación.
        return redirect('socios:detalle_postulacion', postulacion_id=socio.postulaciones.latest('fecha_recepcion').id)

    contacto = socio.contactos.filter(activo=True).order_by('-es_principal', 'pk').first()
    pendiente = socio.estado_revision == 'RECIBIDO'
    form = SocioPropuestoForm(request.POST or None, instance=socio, contacto=contacto)

    if request.method == 'POST' and form.is_valid():
        try:
            decision = services.revisar_socio_propuesto(request, socio, form)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            if decision:
                messages.success(
                    request,
                    f"{socio.nombre_organizacion} quedó "
                    f"{'disponible para otros grupos' if decision == DECISION_HABILITAR else 'solo en el historial del equipo'}.",
                )
                return redirect(f"{reverse('socios:lista_postulaciones')}?origen=equipos")
            messages.success(request, "Datos del socio guardados.")
            return redirect('socios:revisar_socio_propuesto', socio_id=socio.id)

    participaciones = (
        socio.participaciones.filter(equipo__isnull=False)
        .select_related('equipo__seccion__asignatura', 'periodo')
        .prefetch_related('equipo__seccion__seccion_docentes__docente')
        .order_by('fecha_inicio', 'pk')
    )
    return render(request, 'socios/revisar_propuesto.html', {
        'socio': socio,
        'form': form,
        'pendiente': pendiente,
        'participaciones': participaciones,
    })


@coordinador_required
def detalle_postulacion(request, postulacion_id):
    """
    Página de revisión: la ficha que envió el socio, ordenada por sección, y
    la decisión del Coordinador (RF-SC-02).
    """
    postulacion = get_object_or_404(
        PostulacionSocio.objects.select_related(
            'convocatoria', 'respuesta_formulario', 'socio', 'revisado_por_usuario',
        ),
        pk=postulacion_id,
    )

    secciones = []
    for pregunta, texto in encuestas_services.resumen_respuesta(postulacion.respuesta_formulario):
        if not secciones or secciones[-1]['bloque'].id != pregunta.bloque_id:
            secciones.append({'bloque': pregunta.bloque, 'respuestas': []})
        secciones[-1]['respuestas'].append((pregunta, texto))

    return render(request, 'socios/detalle_postulacion.html', {
        'postulacion': postulacion,
        'secciones': secciones,
    })


@coordinador_required
def revisar_postulacion(request, postulacion_id):
    """
    Transición de estado para postulaciones externas con motivo de rechazo obligatorio,
    notificación por correo y registro en auditoría (SP5-T12 / CDE-531).
    """
    postulacion = get_object_or_404(PostulacionSocio, pk=postulacion_id)

    if request.method == "POST":
        nuevo_estado = request.POST.get("estado")
        motivo = request.POST.get("motivo_rechazo", "").strip()

        try:
            services.revisar_postulacion(
                request,
                postulacion,
                nuevo_estado,
                motivo=motivo,
            )
        except ValidationError as error:
            messages.error(request, error.messages[0])
            
            return redirect("socios:detalle_postulacion", postulacion_id=postulacion.id)
        else:
            messages.success(
                request,
                f"Postulación #{postulacion.id} actualizada a "
                f"{etiqueta(ESTADOS_POSTULACION, postulacion.estado).lower()} y notificada.",
            )

  
    return redirect("socios:detalle_postulacion", postulacion_id=postulacion.id)
@docente_required
def asociar_socio_equipo(request, actividad_id):
    actividad = get_object_or_404(
        SeccionActividad.objects.select_related(
            "seccion_ruta",
            "seccion_ruta__seccion",
            "ruta_actividad",
        ),
        id=actividad_id,
    )

    seccion = actividad.seccion_ruta.seccion

    docente = getattr(request.user, "perfil_docente", None)

    if docente is None:
        raise PermissionDenied

    if not seccion.docentes.filter(id=docente.id).exists():
        raise PermissionDenied

  
    if url_recurso(actividad) != reverse(
        "socios:asociar_socio_equipo", args=[actividad.id]
    ):
        raise PermissionDenied

    equipos = (
        Equipo.objects
        .filter(seccion=seccion)
        .con_socio_vigente()
        .prefetch_related("integrantes")
        .order_by("numero_grupo")
    )

    socios = (
        socios_disponibles()
        .select_related(
            "clasificacion",
            "comuna",
        )
        .order_by("nombre_organizacion")
    )

    if request.method == "POST":
        equipo_id = request.POST.get("equipo")
        socio_id = request.POST.get("socio")
        motivo = request.POST.get("motivo", "").strip()

        if not equipo_id or not socio_id:
            messages.error(
                request,
                "Debes seleccionar un equipo y un Socio Comunitario.",
            )
        elif len(motivo) > MAX_LARGO_MOTIVO_CAMBIO_SOCIO:
            # Mismo límite que gestionar_equipo (el motivo queda en la auditoría).
            messages.error(
                request,
                "El motivo del cambio no puede superar "
                f"los {MAX_LARGO_MOTIVO_CAMBIO_SOCIO} caracteres.",
            )
        else:
            equipo = get_object_or_404(
                Equipo,
                id=equipo_id,
                seccion=seccion,
            )

            socio = get_object_or_404(
                socios_disponibles(),
                id=socio_id,
            )

        
            try:
                _, creada = services.asociar_socio_a_equipo(
                    equipo=equipo,
                    socio=socio,
                    docente=docente,
                    motivo=motivo,
                    request=request,
                )
            except ValidationError as error:
                messages.error(request, error.messages[0])

                return redirect(
                    "socios:asociar_socio_equipo",
                    actividad_id=actividad.id,
                )

            if not creada:
                messages.info(
                    request,
                    "El equipo ya tiene asociado este Socio Comunitario.",
                )

                return redirect(
                    "socios:asociar_socio_equipo",
                    actividad_id=actividad.id,
                )

            messages.success(
                request,
                f"El Socio Comunitario fue asociado correctamente al Grupo {equipo.numero_grupo}.",
            )

            return redirect(
                "socios:asociar_socio_equipo",
                actividad_id=actividad.id,
            )

    return render(
        request,
        "socios/asociar_socio_equipo.html",
        {
            "actividad": actividad,
            "seccion": seccion,
            "equipos": equipos,
            "socios": socios,
        },
    )

def postular_publico(request, convocatoria_id=None):
    """
    Formulario público para que un Socio Comunitario postule a una convocatoria A+S.
    Controla vigencia, validación de RUT, duplicados y generación de folio (CDE-49 a CDE-53).
    """
    ahora = timezone.now()
    
    if convocatoria_id:
        convocatoria = get_object_or_404(Convocatoria, pk=convocatoria_id)
    else:
        convocatoria = Convocatoria.objects.filter(
            estado="PUBLICADA",
            fecha_inicio__lte=ahora,
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=ahora)
        ).first()

    if not convocatoria:
        return render(request, "socios/postulacion_cerrada.html", {
            "mensaje": "Actualmente no existen convocatorias abiertas para Socios Comunitarios."
        })

    if convocatoria.fecha_fin and convocatoria.fecha_fin < ahora:
        return render(request, "socios/postulacion_cerrada.html", {
            "convocatoria": convocatoria,
            "mensaje": "Esta convocatoria ha cerrado su período de postulación."
        })

    errores = []

    if request.method == "POST":
        nombre_org = request.POST.get("nombre_organizacion", "").strip()
        rut_raw = request.POST.get("rut", "").strip()
        correo = request.POST.get("correo", "").strip()
        contacto_nombre = request.POST.get("contacto_nombre", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        comuna_id = request.POST.get("comuna")
        clasificacion_id = request.POST.get("clasificacion")
        linea_servicio = request.POST.get("linea_servicio", "").strip()
        detalle_adicional = request.POST.get("detalle_adicional", "").strip()

        if not nombre_org or not rut_raw or not correo or not contacto_nombre:
            errores.append("Debes completar todos los campos obligatorios (*).")

        rut_formateado = None
        try:
            rut_formateado = validar_rut_chileno(rut_raw)
        except ValidationError as e:
            errores.append(e.message)

        if rut_formateado and PostulacionSocio.objects.filter(
            convocatoria=convocatoria,
            respuesta_formulario__respondente_rut=rut_formateado,
            estado__in=["RECIBIDA", "APROBADA"],
        ).exists():
            errores.append(f"Ya existe una postulación registrada para el RUT {rut_formateado} en esta convocatoria.")

        if not errores:
            socio, _ = SocioComunitario.objects.get_or_create(
                rut=rut_formateado,
                defaults={
                    "nombre_organizacion": nombre_org,
                    "estado_revision": "RECIBIDO",
                    "es_provisional": True,
                    "activo": True,
                    "fecha_creacion": ahora,
                    "comuna_id": comuna_id or None,
                    "clasificacion_id": clasificacion_id or None,
                }
            )

            ContactoSocio.objects.get_or_create(
                socio=socio,
                correo=correo,
                defaults={
                    "nombre": contacto_nombre,
                    "telefono": telefono,
                    "es_principal": True,
                    "activo": True,
                }
            )

            resp_form = RespuestaFormulario.objects.create(
                version=convocatoria.formulario_version,
                fecha_envio=ahora,
                origen="PUBLICO",
                es_historica=False,
                respondente_tipo="SOCIO_COMUNITARIO",
                respondente_nombre=contacto_nombre,
                respondente_correo=correo,
                respondente_rut=rut_formateado,
                estado_registro="COMPLETO",
            )

            postulacion = PostulacionSocio.objects.create(
                convocatoria=convocatoria,
                respuesta_formulario=resp_form,
                socio=socio,
                estado="RECIBIDA",
                fecha_recepcion=ahora,
            )

            enviar_notificacion_postulacion(postulacion, tipo_evento="RECEPCION")

            return redirect("socios:postulacion_exitosa", postulacion_id=postulacion.id)

    comunas = Comuna.objects.filter(activo=True).order_by("nombre")
    clasificaciones = ClasificacionSocio.objects.filter(activo=True).order_by("nombre")

    return render(request, "socios/postular_publico.html", {
        "convocatoria": convocatoria,
        "comunas": comunas,
        "clasificaciones": clasificaciones,
        "errores": errores,
    })


def postulacion_exitosa(request, postulacion_id):
    """
    Pantalla de confirmación con identificador, fecha y enlace/QR (CDE-50, CDE-53).
    """
    postulacion = get_object_or_404(
        PostulacionSocio.objects.select_related("convocatoria", "respuesta_formulario", "socio"),
        pk=postulacion_id,
    )
    return render(request, "socios/postulacion_exitosa.html", {
        "postulacion": postulacion,
    })

# Se mantienen por compatibilidad con los enlaces de SP5-T12; el flujo real es postular_publico.
def postular_publico_fijo(request):
    return redirect("socios:postular_publico")


def postulacion_exitosa_fija(request, identificador):
    return redirect("socios:postular_publico")


@coordinador_required
def rechazar_postulacion_fija(request, pk):
    return redirect("socios:lista_postulaciones")
