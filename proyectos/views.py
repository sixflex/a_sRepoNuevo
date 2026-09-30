from datetime import datetime, time

from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from usuarios.decorators import coordinador_required
from planificacion.models import PlanificacionEnlace
from planificacion.email_service import enviar_correo_planificacion
from academico.models import Campus, PeriodoAcademico, UnidadAcademica
from auditoria.services import registrar_auditoria

@coordinador_required
def coordinador_contexto(request):
    return render(request, "proyectos/coordinador_contexto.html")


@coordinador_required
def gestionar_enlaces_planificacion(request):
    if request.method == "POST":
        accion = request.POST.get("accion", "crear")

        if accion == "toggle_estado":
            enlace = get_object_or_404(
                PlanificacionEnlace,
                pk=request.POST.get("enlace_id"),
            )
            estado_anterior = enlace.activo
            enlace.activo = not enlace.activo
            enlace.save(update_fields=["activo"])
            registrar_auditoria(
                request=request,
                entidad="PlanificacionEnlace",
                entidad_id=enlace.id,
                accion=(
                    "ACTIVAR_ENLACE"
                    if enlace.activo
                    else "DESACTIVAR_ENLACE"
                ),
                valores_anteriores={
                    "activo": estado_anterior,
                },
                valores_nuevos={
                    "activo": enlace.activo,
                },
            )

            messages.success(
                request,
                "El enlace fue activado."
                if enlace.activo
                else "El enlace fue desactivado.",
            )
            return redirect("proyectos:gestionar_enlaces")

        if accion == "reenviar":
            enlace = get_object_or_404(
            PlanificacionEnlace,
            pk=request.POST.get("enlace_id"),
            )

            ahora = timezone.now()

            if not enlace.activo:
                messages.error(
                    request,
                    "No se puede reenviar un enlace que está inactivo.",
                )
                return redirect("proyectos:gestionar_enlaces")

            if (
                enlace.fecha_expiracion is not None
                and enlace.fecha_expiracion < ahora
            ):
                messages.error(
                    request,
                    "No se puede reenviar un enlace que ya expiró.",
                )
                return redirect("proyectos:gestionar_enlaces")

            try:
                enviado = enviar_correo_planificacion(
                    request,
                    enlace,
                    reenvio=True,
                )

                if enviado:
                    registrar_auditoria(
                        request=request,
                        entidad="PlanificacionEnlace",
                        entidad_id=enlace.id,
                        accion="REENVIAR_ENLACE",
                        valores_nuevos={
                            "destinatario_correo": enlace.destinatario_correo,
                            "fecha_reenvio": timezone.now().isoformat(),
                        },
                    )
                    messages.success(
                        request,
                        (
                            "El enlace fue reenviado correctamente a "
                            f"{enlace.destinatario_correo}."
                        ),
                    )
                else:
                    messages.error(
                        request,
                        "No fue posible reenviar el enlace.",
                    )

            except Exception:
                messages.error(
                    request,
                    (
                        "No fue posible enviar el correo. "
                        "Revise la configuración del servicio de correo."
                    ),
                )
            return redirect("proyectos:gestionar_enlaces")

        unidad_id = request.POST.get("unidad_academica")
        destinatario_nombre = (request.POST.get("destinatario_nombre") or "").strip()
        destinatario_correo = (request.POST.get("destinatario_email") or "").strip()
        campus_id = request.POST.get("campus")
        periodo_id = request.POST.get("periodo")
        fecha_expiracion_texto = request.POST.get("fecha_expiracion")

        if not all(
            [
                unidad_id,
                destinatario_nombre,
                destinatario_correo,
                campus_id,
                periodo_id,
                fecha_expiracion_texto,
            ]
        ):
            messages.error(
                request,
                "Debe completar todos los campos obligatorios.",
            )
        else:
            try:
                validate_email(destinatario_correo)
            except ValidationError:
                messages.error(
                    request,
                    "El correo del destinatario no tiene un formato válido.",
                )
                return redirect("proyectos:gestionar_enlaces")

            fecha_expiracion = parse_date(fecha_expiracion_texto)

            if fecha_expiracion is None:
                messages.error(
                    request,
                    "La fecha de expiración no es válida.",
                )
                return redirect("proyectos:gestionar_enlaces")

            # La fecha elegida se considera vigente hasta el final de ese día.
            fecha_expiracion_dt = timezone.make_aware(
                datetime.combine(fecha_expiracion, time.max)
            )

            if fecha_expiracion_dt <= timezone.now():
                messages.error(
                    request,
                    "La fecha de expiración debe ser posterior al momento actual.",
                )
                return redirect("proyectos:gestionar_enlaces")

            unidad = get_object_or_404(
                UnidadAcademica,
                pk=unidad_id,
                activo=True,
            )
            campus = get_object_or_404(
                Campus.objects.select_related("sede"),
                pk=campus_id,
                activo=True,
            )
            periodo = get_object_or_404(
                PeriodoAcademico,
                pk=periodo_id,
            )

            enlace = PlanificacionEnlace.objects.create(
                unidad_academica=unidad,
                campus=campus,
                periodo=periodo,
                destinatario_nombre=destinatario_nombre,
                destinatario_correo=destinatario_correo,
                fecha_emision=timezone.now(),
                fecha_expiracion=fecha_expiracion_dt,
                activo=True,
            )
            registrar_auditoria(
                request=request,
                entidad="PlanificacionEnlace",
                entidad_id=enlace.id,
                accion="CREAR_ENLACE",
                valores_nuevos={
                    "unidad_academica_id": enlace.unidad_academica_id,
                    "campus_id": enlace.campus_id,
                    "periodo_id": enlace.periodo_id,
                    "destinatario_nombre": enlace.destinatario_nombre,
                    "destinatario_correo": enlace.destinatario_correo,
                    "fecha_expiracion": (
                        enlace.fecha_expiracion.isoformat()
                        if enlace.fecha_expiracion
                        else None
                    ),
                    "activo": enlace.activo,
                },
            )
            try:
                enviado = enviar_correo_planificacion(
                    request,
                    enlace,
                    reenvio=False,
                )

                if enviado:
                    messages.success(
                        request,
                        (
                            f"Enlace generado y enviado correctamente a "
                            f"{destinatario_correo}."
                        ),
                    )
                else:
                    messages.warning(
                        request,
                        (
                            "El enlace fue generado correctamente, "
                            "pero no pudo enviarse por correo."
                        ),
                    )

            except Exception:
                messages.warning(
                    request,
                    (
                        "El enlace fue generado correctamente, "
                        "pero no pudo enviarse por correo. "
                        "Puede copiarlo manualmente desde la lista."
                    ),
                )

            return redirect("proyectos:gestionar_enlaces")

    enlaces = list(
        PlanificacionEnlace.objects.select_related(
            "unidad_academica",
            "unidad_academica__facultad",
            "unidad_academica__carrera",
            "campus__sede",
            "periodo",
        ).order_by("-fecha_emision", "-id")
    )

    ahora = timezone.now()
    for enlace in enlaces:
        enlace.esta_vigente = (
            enlace.activo
            and (
                enlace.fecha_expiracion is None
                or enlace.fecha_expiracion >= ahora
            )
        )

    unidades = (
        UnidadAcademica.objects.filter(activo=True)
        .select_related("facultad", "carrera")
        .order_by("tipo", "nombre")
    )
    campus = (
        Campus.objects.filter(activo=True)
        .select_related("sede")
        .order_by("sede__nombre", "nombre")
    )
    periodos = PeriodoAcademico.objects.all().order_by(
        "-anio",
        "tipo",
        "nombre",
    )

    return render(
        request,
        "proyectos/gestionar_enlaces.html",
        {
            "enlaces": enlaces,
            "unidades": unidades,
            "campus": campus,
            "periodos": periodos,
            "hoy": timezone.localdate().isoformat(),
        },
    )
