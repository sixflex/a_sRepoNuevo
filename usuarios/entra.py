"""Conector de identidad Entra ID (SP5-T02).

Hoy solo existe la versión SIMULADA. El resto del sistema (vistas, pruebas)
habla con el conector únicamente a través de ``get_conector().identificar()``,
así que para conectar un tenant real basta con escribir otra clase con ese mismo
método y apuntar a ella con ``ENTRA_CONECTOR``.

Configuración (en settings.py o como variables de entorno en .env):

    ENTRA_MODO               "simulado" | "desactivado".
                             Por defecto "simulado" solo si DEBUG=True.
    ENTRA_DOMINIOS_PERMITIDOS  Dominios separados por coma.
                             Por defecto "uautonoma.cl,cloud.uautonoma.cl"
                             (funcionarios y docentes/estudiantes).
    ENTRA_DOMINIO_PERMITIDO  Antiguo, un solo dominio. Si está definido manda.
    ENTRA_CONECTOR           Ruta de la clase conector. Por defecto el simulado.

Una persona puede tener las dos cuentas; ambas llegan al mismo Usuario
(ver usuarios/services.py).
"""
import os
import re
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string


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
    # La misma persona que docente@uautonoma.cl, con su cuenta cloud. No viene
    # vinculada: sirve para probar "Vincular otra cuenta" en /cuenta/.
    {"correo": "docente@cloud.uautonoma.cl", "nombre": "Docente Prueba", "rol": ROL_DOCENTE},
    {"correo": "estudiante@cloud.uautonoma.cl", "nombre": "Estudiante Cloud", "rol": ROL_ESTUDIANTE},
)

TENANT_SIMULADO = "simulado"
DOMINIOS_POR_DEFECTO = "uautonoma.cl,cloud.uautonoma.cl"


class EntraError(Exception):
    """Acceso rechazado. El mensaje se puede mostrar al usuario."""


@dataclass(frozen=True)
class IdentidadEntra:
    oid: str
    correo: str
    nombre: str
    apellido: str
    rol: str
    tenant_id: str = TENANT_SIMULADO


def modo():
    valor = getattr(settings, "ENTRA_MODO", None) or os.getenv("ENTRA_MODO")
    if valor:
        return valor.lower()
    return "simulado" if settings.DEBUG else "desactivado"


def dominios_permitidos():
    """Dominios aceptados, en orden. El antiguo ENTRA_DOMINIO_PERMITIDO manda si existe."""
    valor = (
        getattr(settings, "ENTRA_DOMINIO_PERMITIDO", None)
        or os.getenv("ENTRA_DOMINIO_PERMITIDO")
        or getattr(settings, "ENTRA_DOMINIOS_PERMITIDOS", None)
        or os.getenv("ENTRA_DOMINIOS_PERMITIDOS", DOMINIOS_POR_DEFECTO)
    )
    dominios = [d.strip().lower().lstrip("@") for d in valor.split(",")]
    return [d for d in dominios if d]


def dominio_permitido():
    """Primer dominio permitido (se usa en ejemplos de texto)."""
    return dominios_permitidos()[0]


def texto_dominios():
    """'@uautonoma.cl o @cloud.uautonoma.cl'."""
    dominios = [f"@{d}" for d in dominios_permitidos()]
    if len(dominios) == 1:
        return dominios[0]
    return ", ".join(dominios[:-1]) + " o " + dominios[-1]


def oid_simulado(correo):
    """El mismo correo siempre genera el mismo oid de prueba."""
    return "sim-" + str(uuid.uuid5(_NAMESPACE_OID, correo.strip().lower()))


class ConectorEntraSimulado:
    """Hace de Entra ID: valida el dominio y entrega una identidad de prueba."""

    def identificar(self, correo):
        correo = (correo or "").strip().lower()

        if not _PATRON_CORREO.match(correo):
            raise EntraError("Escribe un correo válido, por ejemplo nombre@uautonoma.cl.")

        dominio = correo.rsplit("@", 1)[1]
        if dominio not in dominios_permitidos():
            raise EntraError(
                f"Solo se permiten cuentas institucionales {texto_dominios()}."
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
            oid=oid_simulado(correo),
            correo=correo,
            nombre=nombre,
            apellido=apellido,
            rol=rol,
            tenant_id=TENANT_SIMULADO,
        )


def get_conector():
    ruta = getattr(settings, "ENTRA_CONECTOR", None) or os.getenv(
        "ENTRA_CONECTOR", "usuarios.entra.ConectorEntraSimulado"
    )
    return import_string(ruta)()


def autenticar_con_entra(correo):
    """
    Valida el correo con el conector y devuelve (usuario, identidad) locales.
    Crea el usuario si es su primera vez.
    """
    from .services import obtener_o_crear_usuario_por_identidad

    identidad = get_conector().identificar(correo)
    return obtener_o_crear_usuario_por_identidad(identidad)
