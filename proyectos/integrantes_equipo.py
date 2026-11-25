"""
El docente agrega o quita integrantes de un equipo ya registrado
(RF-EQP-07: revisar y corregir los equipos, con autor, fecha y valores
anterior y nuevo en la auditoría).

El equipo no depende de quien lo registró: si sale el informante, el equipo,
su socio y el trabajo con el socio siguen siendo de los que quedan, y
cualquiera de ellos puede volver al enlace del registro.
"""

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from auditoria.services import registrar_auditoria
from core.textos import nombre_persona
from core.validators import es_rut_valido, normalizar_rut

from .models import IntegranteEquipo

MAXIMO = 6


def _nombre(texto):
    return nombre_persona(texto)


def _datos(integrante):
    return {
        "rut": integrante.rut, "nombres": integrante.nombres, "apellidos": integrante.apellidos,
        "correo_institucional": integrante.correo_institucional, "es_informante": integrante.es_informante,
    }


def agregar(equipo, post, request):
    """Devuelve la lista de errores; vacía si se agregó."""
    nombres = _nombre(post.get("nombres"))
    apellidos = _nombre(post.get("apellidos"))
    rut = (post.get("rut") or "").strip()
    correo = (post.get("correo") or "").strip().lower()

    errores = []
    if equipo.integrantes.count() >= MAXIMO:
        errores.append(f"Un equipo tiene como máximo {MAXIMO} integrantes.")
    if not nombres or not apellidos:
        errores.append("Los nombres y apellidos son obligatorios.")
    if not rut or not es_rut_valido(rut):
        errores.append("El RUT no es válido.")
    try:
        validate_email(correo)
    except ValidationError:
        errores.append("El correo institucional no es válido.")
    if errores:
        return errores

    rut = normalizar_rut(rut)
    en_la_seccion = IntegranteEquipo.objects.filter(equipo__seccion=equipo.seccion)
    if en_la_seccion.filter(rut=rut).exists():
        errores.append("Ese RUT ya está en un equipo de esta sección.")
    if en_la_seccion.filter(correo_institucional__iexact=correo).exists():
        errores.append("Ese correo ya está en un equipo de esta sección.")
    if errores:
        return errores

    integrante = IntegranteEquipo.objects.create(
        equipo=equipo, rut=rut, nombres=nombres[:120], apellidos=apellidos[:120],
        correo_institucional=correo, es_informante=False,
    )
    registrar_auditoria(
        request=request, entidad="Equipo", entidad_id=equipo.pk,
        accion="AGREGAR_INTEGRANTE", valores_nuevos=_datos(integrante),
    )
    return []


def quitar(equipo, integrante, request):
    """Devuelve un mensaje de error, o None si se quitó."""
    if equipo.integrantes.count() <= 1:
        return "El equipo debe quedar con al menos un integrante."
    anteriores = _datos(integrante)
    integrante.delete()
    registrar_auditoria(
        request=request, entidad="Equipo", entidad_id=equipo.pk,
        accion="QUITAR_INTEGRANTE", valores_anteriores=anteriores,
    )
    return None
