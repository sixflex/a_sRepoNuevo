"""Conector de identidad Entra ID (SP5-T02).

Hoy solo existe la versión SIMULADA. El resto del sistema (vistas, pruebas)
habla con el conector únicamente a través de ``get_conector().identificar()``,
así que para conectar un tenant real basta con escribir otra clase con ese mismo
método y apuntar a ella con ``ENTRA_CONECTOR``.

Configuración (en settings.py o como variables de entorno en .env):

    ENTRA_MODO               "simulado" | "desactivado".
                             Por defecto "simulado" solo si DEBUG=True.
    ENTRA_DOMINIO_PERMITIDO  Por defecto "uautonoma.cl".
    ENTRA_CONECTOR           Ruta de la clase conector. Por defecto el simulado.
"""
import os
import re
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import Rol


ROL_COORDINADOR = "Coordinador"
ROL_DOCENTE = "Docente"
ROL_ESTUDIANTE = "Estudiante"

# Namespace fijo: el mismo correo siempre genera el mismo entra_oid de prueba.
_NAMESPACE_OID = uuid.UUID("6f1c7b52-3b0e-4a43-9c55-0a5f6a1d2b10")

_PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Cuentas de prueba que se ofrecen en la pantalla simulada.
CUENTAS_PRUEBA = (
    {"correo": "coordinador@uautonoma.cl", "nombre": "Coordinador Prueba", "rol": ROL_COORDINADOR},
    {"correo": "docente@uautonoma.cl", "nombre": "Docente Prueba", "rol": ROL_DOCENTE},
    {"correo": "estudiante@uautonoma.cl", "nombre": "Estudiante Prueba", "rol": ROL_ESTUDIANTE},
)


class EntraError(Exception):
    """Acceso rechazado. El mensaje se puede mostrar al usuario."""


@dataclass(frozen=True)
class IdentidadEntra:
    oid: str
    correo: str
    nombre: str
    apellido: str
    rol: str


def modo():
    valor = getattr(settings, "ENTRA_MODO", None) or os.getenv("ENTRA_MODO")
    if valor:
        return valor.lower()
    return "simulado" if settings.DEBUG else "desactivado"


def dominio_permitido():
    valor = getattr(settings, "ENTRA_DOMINIO_PERMITIDO", None) or os.getenv(
        "ENTRA_DOMINIO_PERMITIDO", "uautonoma.cl"
    )
    return valor.strip().lower().lstrip("@")


class ConectorEntraSimulado:
    """Hace de Entra ID: valida el dominio y entrega una identidad de prueba."""

    def identificar(self, correo):
        correo = (correo or "").strip().lower()

        if not _PATRON_CORREO.match(correo):
            raise EntraError("Escribe un correo válido, por ejemplo nombre@uautonoma.cl.")

        dominio = correo.rsplit("@", 1)[1]
        if dominio != dominio_permitido():
            raise EntraError(
                f"Solo se permiten cuentas institucionales @{dominio_permitido()}."
            )

        cuenta = next((c for c in CUENTAS_PRUEBA if c["correo"] == correo), None)
        if cuenta:
            rol = cuenta["rol"]
            nombre, _, apellido = cuenta["nombre"].partition(" ")
        else:
            # Cuenta institucional sin rol asignado: entra con el rol de menor privilegio.
            rol = ROL_ESTUDIANTE
            nombre, apellido = correo.split("@", 1)[0], ""

        return IdentidadEntra(
            oid="sim-" + str(uuid.uuid5(_NAMESPACE_OID, correo)),
            correo=correo,
            nombre=nombre,
            apellido=apellido,
            rol=rol,
        )


def get_conector():
    ruta = getattr(settings, "ENTRA_CONECTOR", None) or os.getenv(
        "ENTRA_CONECTOR", "usuarios.entra.ConectorEntraSimulado"
    )
    return import_string(ruta)()


def autenticar_con_entra(correo):
    """Valida el correo con el conector y devuelve el usuario local (lo crea si falta)."""
    identidad = get_conector().identificar(correo)
    return _provisionar_usuario(identidad)


def _provisionar_usuario(identidad):
    Usuario = get_user_model()

    with transaction.atomic():
        usuario = (
            Usuario.objects.filter(entra_oid=identidad.oid).first()
            or Usuario.objects.filter(correo_institucional__iexact=identidad.correo).first()
            or Usuario.objects.filter(username__iexact=identidad.correo).first()
        )

        if usuario is None:
            usuario = Usuario(
                username=identidad.correo,
                email=identidad.correo,
                first_name=identidad.nombre,
                last_name=identidad.apellido,
            )
            usuario.set_unusable_password()

        if not usuario.is_active or not usuario.activo:
            raise EntraError("Tu cuenta está desactivada. Contacta a la coordinación.")

        if not usuario.entra_oid:
            usuario.entra_oid = identidad.oid
        if not usuario.correo_institucional:
            usuario.correo_institucional = identidad.correo
        if not usuario.rol_id:
            usuario.rol, _ = Rol.objects.get_or_create(nombre=identidad.rol)

        usuario.fecha_ultimo_acceso = timezone.now()
        usuario.save()

        # El menú lateral y los decoradores trabajan con grupos de Django.
        if not usuario.groups.exists():
            grupo, _ = Group.objects.get_or_create(name=identidad.rol)
            usuario.groups.add(grupo)

    return usuario
