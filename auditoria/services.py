from django.utils import timezone
from .models import AuditoriaCambio

def obtener_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")

def registrar_auditoria(
    *,
    request=None,
    entidad,
    entidad_id,
    accion,
    valores_anteriores=None,
    valores_nuevos=None,
    actor_externo=None,
):
    usuario = None
    ip = None

    if request is not None:
        ip = obtener_ip(request)

        if (
            hasattr(request, "user")
            and request.user.is_authenticated
        ):
            usuario = request.user

    return AuditoriaCambio.objects.create(
        usuario=usuario,
        actor_externo=actor_externo,
        entidad=entidad,
        entidad_id=str(entidad_id),
        accion=accion,
        valores_anteriores_json=valores_anteriores,
        valores_nuevos_json=valores_nuevos,
        fecha=timezone.now(),
        ip=ip,
    )