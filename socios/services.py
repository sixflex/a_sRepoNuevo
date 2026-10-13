from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from academico.models import Docente
from comunicaciones.models import EnvioCorreo
from proyectos.models import Equipo

from auditoria.models import AuditoriaCambio
from auditoria.services import registrar_auditoria

from .constantes import (
    ESTADOS_POSTULACION,
    ESTADOS_SOCIO,
    ORIGEN_OPERATIVO,
    estados_siguientes,
    etiqueta,
)
from .models import ParticipacionSocio, SocioComunitario

# Responsable y fecha de cada cambio (RF-SC-02 CA2) se registran en
# AUDITORIA_CAMBIO, como indica el modelo de BD aprobado.
ENTIDAD_SOCIO = "SocioComunitario"
ACCION_CAMBIO_ESTADO_SOCIO = "CAMBIO_ESTADO_SOCIO"
ENTIDAD_POSTULACION = "PostulacionSocio"
ACCION_REVISION_POSTULACION = "REVISION_POSTULACION"
ENTIDAD_EQUIPO = "Equipo"
ACCION_CAMBIO_SOCIO_EQUIPO = "CAMBIO_SOCIO_EQUIPO"

# Decisión sobre la postulación -> estado del socio (RF-SC-02)
ESTADO_SOCIO_SEGUN_DECISION = {
    "APROBADA": "APROBADO",
    "RECHAZADA": "RECHAZADO",
}

# Estados del socio desde los que la decisión lo mueve
ESTADOS_EN_REVISION = {
    "APROBADA": ("RECIBIDO", "RECHAZADO"),
    "RECHAZADA": ("RECIBIDO",),
}

TEXTO_INVITACION = (
    "Agradecemos su participación en el programa de Aprendizaje + Servicio "
    "y le invitamos a postular en una próxima convocatoria."
)


def correo_contacto_principal(socio):
    if socio is None:
        return None
    contacto = socio.contactos.filter(es_principal=True, activo=True).exclude(correo="").first()
    return contacto.correo if contacto and contacto.correo else None


def historial_estados_socio(socio):
    """Cambios de estado del socio registrados en auditoría, del más reciente al más antiguo."""
    return (
        AuditoriaCambio.objects
        .filter(entidad=ENTIDAD_SOCIO, entidad_id=str(socio.pk), accion=ACCION_CAMBIO_ESTADO_SOCIO)
        .select_related("usuario")
        .order_by("-fecha", "-id")
    )


def _registrar_cambio(request, socio, nuevo_estado, es_provisional=None, extra=None):
    """
    Aplica el cambio al socio y lo deja en auditoría con responsable y fecha.
    Devuelve el registro de auditoría, o None si no hubo cambios.
    """
    if es_provisional is None:
        es_provisional = socio.es_provisional

    if socio.estado_revision == nuevo_estado and socio.es_provisional == es_provisional:
        return None

    anteriores = {"estado_revision": socio.estado_revision, "es_provisional": socio.es_provisional}
    nuevos = {"estado_revision": nuevo_estado, "es_provisional": es_provisional}
    nuevos.update(extra or {})

    socio.estado_revision = nuevo_estado
    socio.es_provisional = es_provisional
    socio.save(update_fields=["estado_revision", "es_provisional"])

    return registrar_auditoria(
        request=request,
        entidad=ENTIDAD_SOCIO,
        entidad_id=socio.pk,
        accion=ACCION_CAMBIO_ESTADO_SOCIO,
        valores_anteriores=anteriores,
        valores_nuevos=nuevos,
    )


def postulacion_pendiente(socio):
    return socio.postulaciones.filter(estado="RECIBIDA").order_by("fecha_recepcion").first()


def cambiar_estado_socio(request, socio, nuevo_estado, es_provisional=None, motivo=""):
    """
    Cambio de estado hecho desde el catálogo del coordinador.
    Devuelve el registro de auditoría, o None si no hubo cambios.
    Lanza ValidationError si el cambio no está permitido.
    """
    motivo = (motivo or "").strip()

    if nuevo_estado not in dict(ESTADOS_SOCIO):
        raise ValidationError("El estado seleccionado no es válido.")

    pendiente = postulacion_pendiente(socio)
    if pendiente:
        raise ValidationError(
            f"{socio.nombre_organizacion} tiene una postulación pendiente (folio #{pendiente.id}). "
            "Apruébela o recházela en Socios comunitarios › Postulaciones; "
            "esa revisión actualiza el estado del socio."
        )

    if nuevo_estado not in dict(estados_siguientes(socio.estado_revision)):
        raise ValidationError(
            f"Un socio en estado «{etiqueta(ESTADOS_SOCIO, socio.estado_revision)}» no puede pasar a "
            f"«{etiqueta(ESTADOS_SOCIO, nuevo_estado)}»."
        )

    rechaza = nuevo_estado == "RECHAZADO" and socio.estado_revision != "RECHAZADO"
    if rechaza and not motivo:
        raise ValidationError("Debes indicar un motivo para rechazar al socio.")

    with transaction.atomic():
        registro = _registrar_cambio(
            request,
            socio,
            nuevo_estado,
            es_provisional,
            extra={"origen": "catalogo", **({"motivo_rechazo": motivo} if rechaza else {})},
        )

    if registro and rechaza:
        enviar_notificacion_rechazo_socio(socio, motivo)

    return registro


def contexto_academico_equipo(equipo):
    """
    Contexto académico que realmente se conoce del equipo (RF-SC-06).
    La sede sale del campus de la sección; la carrera solo se informa si la
    sección pertenece a una única carrera.
    """
    seccion = equipo.seccion
    carreras = list(seccion.seccion_carreras.values_list("carrera_id", flat=True)[:2])
    return {
        "proyecto_id": equipo.proyecto_id,
        "seccion_id": seccion.pk,
        "asignatura_id": seccion.asignatura_id,
        "periodo_id": seccion.periodo_id,
        "campus_id": seccion.campus_id,
        "sede_id": seccion.campus.sede_id,
        "carrera_id": carreras[0] if len(carreras) == 1 else None,
    }


def _nombre_docente(docente):
    if docente is None:
        return None
    return f"{docente.nombres} {docente.apellidos}".strip()


def asociar_socio_a_equipo(*, equipo, socio, docente=None, motivo=None, request=None):
    """
    Asocia un Socio Comunitario a un equipo (RN-09, RF-EQP-08, RF-SC-06).

    ParticipacionSocio es la fuente de verdad: se cierra la participación
    vigente (fecha_fin = hoy) y se abre una nueva OPERATIVA con el contexto
    académico del equipo. El cambio queda en AUDITORIA_CAMBIO con todo lo
    que mostraba el antiguo historial: socio anterior y nuevo (id y nombre),
    docente que lo hizo (id y nombre) y motivo.

    Devuelve (participacion, creada). creada es False si el equipo ya tenía
    ese socio vigente. Lanza ValidationError si otra operación simultánea
    dejó al equipo con una asociación vigente distinta.
    """
    motivo = (motivo or "").strip() or None

    try:
        with transaction.atomic():
            equipo_bloqueado = (
                Equipo.objects
                .select_for_update()
                .select_related("seccion", "seccion__campus")
                .get(pk=equipo.pk)
            )

            actual = (
                ParticipacionSocio.objects
                .filter(equipo=equipo_bloqueado, fecha_fin__isnull=True)
                .select_related("socio")
                .first()
            )

            if actual and actual.socio_id == socio.pk:
                return actual, False

            hoy = timezone.localdate()

            if actual:
                actual.fecha_fin = hoy
                actual.save(update_fields=["fecha_fin"])

            nueva = ParticipacionSocio.objects.create(
                socio=socio,
                equipo=equipo_bloqueado,
                fecha_inicio=hoy,
                fecha_fin=None,
                origen=ORIGEN_OPERATIVO,
                **contexto_academico_equipo(equipo_bloqueado),
            )

            registrar_auditoria(
                request=request,
                entidad=ENTIDAD_EQUIPO,
                entidad_id=equipo_bloqueado.pk,
                accion=ACCION_CAMBIO_SOCIO_EQUIPO,
                valores_anteriores={
                    "socio_comunitario_id": actual.socio_id if actual else None,
                    "socio_nombre": actual.socio.nombre_organizacion if actual else None,
                    "participacion_id": actual.pk if actual else None,
                },
                valores_nuevos={
                    "socio_comunitario_id": socio.pk,
                    "socio_nombre": socio.nombre_organizacion,
                    "participacion_id": nueva.pk,
                    "motivo": motivo,
                    "docente_id": docente.pk if docente else None,
                    "docente_nombre": _nombre_docente(docente),
                },
            )
    except IntegrityError as error:
        raise ValidationError(
            "No fue posible actualizar la asociación del equipo porque cambió "
            "mientras se guardaba. Inténtalo nuevamente."
        ) from error

    # El objeto del llamador muestra de inmediato el socio nuevo.
    equipo.__dict__["socio_vigente"] = socio
    return nueva, True


def historial_socios_equipo(equipo):
    """
    Cambios de socio hechos por un docente sobre el equipo, del más reciente
    al más antiguo, leídos de AUDITORIA_CAMBIO (incluye los copiados desde
    el antiguo HistorialSocioEquipo por la migración socios.0005).

    Cada fila tiene los mismos atributos que usaba la tabla de
    gestionar_equipo: fecha_cambio, socio_anterior, socio_nuevo,
    cambiado_por_docente (nombres/apellidos) y motivo. Como antes, el
    registro inicial que hace el estudiante (sin docente) no aparece.
    """
    registros = []
    for auditoria in (
        AuditoriaCambio.objects
        .filter(entidad=ENTIDAD_EQUIPO, entidad_id=str(equipo.pk), accion=ACCION_CAMBIO_SOCIO_EQUIPO)
        .order_by("-fecha", "-id")
    ):
        anteriores = auditoria.valores_anteriores_json if isinstance(auditoria.valores_anteriores_json, dict) else {}
        nuevos = auditoria.valores_nuevos_json if isinstance(auditoria.valores_nuevos_json, dict) else {}
        if not nuevos.get("docente_id"):
            continue
        registros.append((auditoria, anteriores, nuevos))

    ids_socios = {
        valores.get("socio_comunitario_id")
        for _, anteriores, nuevos in registros
        for valores in (anteriores, nuevos)
    } - {None}
    socios = SocioComunitario.objects.in_bulk(ids_socios)
    docentes = Docente.objects.in_bulk({nuevos["docente_id"] for _, _, nuevos in registros})

    def socio(valores):
        socio_id = valores.get("socio_comunitario_id")
        if socio_id is None:
            return None
        return socios.get(socio_id) or SimpleNamespace(
            pk=socio_id, nombre_organizacion=valores.get("socio_nombre") or f"Socio #{socio_id}",
        )

    filas = []
    for auditoria, anteriores, nuevos in registros:
        docente = docentes.get(nuevos["docente_id"]) or SimpleNamespace(
            pk=nuevos["docente_id"], nombres=nuevos.get("docente_nombre") or "", apellidos="",
        )
        filas.append(SimpleNamespace(
            pk=auditoria.pk,
            fecha_cambio=auditoria.fecha,
            socio_anterior=socio(anteriores),
            socio_nuevo=socio(nuevos),
            cambiado_por_docente=docente,
            motivo=nuevos.get("motivo"),
        ))
    return filas


def revisar_postulacion(request, postulacion, decision, motivo=""):
    """
    Decide una postulación Recibida (Aprobada o Rechazada) y actualiza en el
    mismo paso el estado del socio, con auditoría y correo (RF-SC-02).
    """
    motivo = (motivo or "").strip()

    if decision not in ESTADO_SOCIO_SEGUN_DECISION:
        raise ValidationError("La decisión seleccionada no es válida.")
    if postulacion.estado != "RECIBIDA":
        raise ValidationError(
            f"La postulación #{postulacion.id} ya fue revisada "
            f"({etiqueta(ESTADOS_POSTULACION, postulacion.estado).lower()})."
        )
    if decision == "RECHAZADA" and not motivo:
        raise ValidationError("Debes indicar un motivo de rechazo.")

    with transaction.atomic():
        estado_anterior = postulacion.estado
        postulacion.estado = decision
        postulacion.motivo_rechazo = motivo if decision == "RECHAZADA" else None
        postulacion.revisado_por_usuario = request.user
        postulacion.fecha_revision = timezone.now()
        postulacion.save()

        registrar_auditoria(
            request=request,
            entidad=ENTIDAD_POSTULACION,
            entidad_id=postulacion.pk,
            accion=ACCION_REVISION_POSTULACION,
            valores_anteriores={"estado": estado_anterior},
            valores_nuevos={"estado": decision, "motivo_rechazo": postulacion.motivo_rechazo},
        )

        socio = postulacion.socio
        # Solo se mueve al socio que sigue en revisión: un socio ya disponible
        # que postula a otra convocatoria conserva su estado.
        if socio and socio.estado_revision in ESTADOS_EN_REVISION[decision]:
            # Aprobar deja al socio como definitivo; rechazar no cambia esa marca.
            extra = {"origen": f"postulacion #{postulacion.pk}"}
            if decision == "RECHAZADA":
                extra["motivo_rechazo"] = motivo
            _registrar_cambio(
                request,
                socio,
                ESTADO_SOCIO_SEGUN_DECISION[decision],
                es_provisional=False if decision == "APROBADA" else None,
                extra=extra,
            )

    enviar_notificacion_postulacion(postulacion, tipo_evento=decision, motivo=motivo)
    return postulacion


def _enviar_y_registrar(destinatario, asunto, cuerpo, postulacion=None):
    remitente = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@uautonoma.cl")
    resultado = "PENDIENTE"
    detalle_error = None

    try:
        send_mail(asunto, cuerpo, remitente, [destinatario], fail_silently=False)
        resultado = "OK"
    except Exception as exc:
        resultado = "ERROR"
        detalle_error = str(exc)

    return EnvioCorreo.objects.create(
        postulacion=postulacion,
        remitente=remitente,
        destinatario=destinatario,
        asunto=asunto,
        cuerpo=cuerpo,
        fecha_envio=timezone.now(),
        resultado=resultado,
        detalle_error=detalle_error,
        numero_intento=1,
    )


def enviar_notificacion_rechazo_socio(socio, motivo):
    """Mismo mensaje de rechazo (RF-SC-02 CA1) cuando se decide desde el catálogo."""
    destinatario = correo_contacto_principal(socio)
    if not destinatario:
        return None

    asunto = f"Estado de su registro como Socio Comunitario A+S - {socio.nombre_organizacion}"
    cuerpo = (
        f"Estimado(a) representante de {socio.nombre_organizacion},\n\n"
        f"Le informamos que su registro como Socio Comunitario del programa A+S "
        f"no ha sido aprobado en esta oportunidad.\n\n"
        f"Motivo institucional:\n{motivo}\n\n"
        f"{TEXTO_INVITACION}"
    )
    return _enviar_y_registrar(destinatario, asunto, cuerpo)

def enviar_notificacion_postulacion(postulacion, tipo_evento, motivo=None):
    """
    Envía notificación y registra la auditoría en EnvioCorreo (CDE-55, CDE-56).
    """
    correo_destinatario = None
    if hasattr(postulacion, "respuesta_formulario") and postulacion.respuesta_formulario:
        correo_destinatario = postulacion.respuesta_formulario.respondente_correo

    if not correo_destinatario:
        correo_destinatario = correo_contacto_principal(postulacion.socio)

    if not correo_destinatario:
        return None

    if tipo_evento == "RECEPCION":
        asunto = f"Confirmación de Postulación A+S - Folio #{postulacion.id}"
        cuerpo = (
            f"Estimado(a) postulante,\n\n"
            f"Confirmamos la recepción de su postulación a la convocatoria "
            f"'{postulacion.convocatoria.nombre}'.\n"
            f"Identificador de seguimiento: #{postulacion.id}\n"
            f"Fecha de recepción: {postulacion.fecha_recepcion.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"El equipo de Coordinación A+S revisará sus antecedentes."
        )
    elif tipo_evento == "APROBADA":
        asunto = f"Postulación A+S Aprobada - Folio #{postulacion.id}"
        cuerpo = (
            f"Estimado(a) Socio Comunitario,\n\n"
            f"Nos complace informarle que su postulación a la convocatoria "
            f"'{postulacion.convocatoria.nombre}' ha sido APROBADA.\n\n"
            f"Pronto un docente o coordinador se contactará con usted para coordinar el trabajo conjunto."
        )
    elif tipo_evento == "RECHAZADA":
        asunto = f"Estado de Postulación A+S - Folio #{postulacion.id}"
        cuerpo = (
            f"Estimado(a) postulante,\n\n"
            f"Le informamos que su postulación a la convocatoria "
            f"'{postulacion.convocatoria.nombre}' no ha sido seleccionada en esta oportunidad.\n\n"
            f"Motivo institucional:\n{motivo or 'Sin motivo especificado.'}\n\n"
            f"{TEXTO_INVITACION}"
        )
    else:
        return None

    return _enviar_y_registrar(correo_destinatario, asunto, cuerpo, postulacion=postulacion)
