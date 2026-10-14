from django.contrib import messages
from django.db.models import Exists, OuterRef, Q
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

from django.core.exceptions import ValidationError
from encuestas.models import EnlaceFormulario, FormularioVersion, RespuestaFormulario
from .models import Convocatoria, PostulacionSocio, SocioComunitario, ContactoSocio, Comuna, ClasificacionSocio
from . import services
from .constantes import ESTADOS_POSTULACION, ESTADOS_SOCIO_SELECCIONABLES, estados_siguientes, etiqueta
from .services import enviar_notificacion_postulacion
from .validators import validar_rut_chileno

from .models import (
    ClasificacionSocio,
    Comuna,
    ParticipacionSocio,
    PostulacionSocio,
    SocioComunitario,
)

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

    if q:
        socios = socios.filter(
            Q(nombre_organizacion__icontains=q) |
            Q(rut__icontains=q)
        )
    if comuna_id:
        socios = socios.filter(comuna_id=comuna_id)
    if clasificacion_id:
        socios = socios.filter(clasificacion_id=clasificacion_id)

    context = {
        'socios': socios,
        'comunas': Comuna.objects.filter(activo=True),
        'clasificaciones': ClasificacionSocio.objects.filter(activo=True),
        'q': q,
        'comuna_id': comuna_id,
        'clasificacion_id': clasificacion_id,
    }
    return render(request, 'socios/catalogo_docente.html', context)


@coordinador_required
def lista_socios_coordinador(request):
    """
    Panel completo de búsqueda, filtros combinados y revisión para el Coordinador.
    """
    socios = SocioComunitario.objects.all().select_related('clasificacion', 'comuna').annotate(
        tiene_postulacion_pendiente=Exists(
            PostulacionSocio.objects.filter(socio=OuterRef('pk'), estado="RECIBIDA")
        )
    )

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
        'comunas': Comuna.objects.filter(activo=True),
        'sedes': Sede.objects.filter(activo=True),
        'campus_list': Campus.objects.filter(activo=True),
        'carreras': Carrera.objects.filter(activo=True),
        'periodos': PeriodoAcademico.objects.all(),
        'anios': PeriodoAcademico.objects.values_list('anio', flat=True).distinct().order_by('-anio'),
        'filtros': request.GET,
        'estados_socio': services.ESTADOS_SOCIO,
        'total_participaciones': total_participaciones,
        'total_organizaciones_con_participacion': total_organizaciones_con_participacion,
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
    Muestra las postulaciones enviadas desde convocatorias de socios comunitarios.
    """
    postulaciones = PostulacionSocio.objects.select_related(
        'convocatoria', 'respuesta_formulario', 'socio', 'revisado_por_usuario'
    ).order_by('-fecha_recepcion')

    return render(request, 'socios/lista_postulaciones.html', {'postulaciones': postulaciones})


@coordinador_required
def revisar_postulacion(request, postulacion_id):
    """
    Transición de estado para postulaciones externas con motivo de rechazo,
    notificación por correo y registro en auditoría (CDE-54, CDE-55, CDE-56).
    """
    postulacion = get_object_or_404(PostulacionSocio, pk=postulacion_id)

    if request.method == "POST":
        decision = request.POST.get("estado")
        try:
            services.revisar_postulacion(
                request,
                postulacion,
                decision,
                motivo=request.POST.get("motivo_rechazo", ""),
            )
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(
                request,
                f"Postulación #{postulacion.id} {etiqueta(ESTADOS_POSTULACION, postulacion.estado).lower()} y notificada.",
            )

    return redirect('socios:lista_postulaciones')

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

    # Solo la actividad de la Ruta configurada con esta acción (recurso_url).
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

            # Servicio común (RN-09, RF-EQP-08); el motivo es opcional aquí.
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
