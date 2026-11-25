"""Conector de identidad Entra ID (SP5-T02).

Hay dos conectores:

- ConectorEntraSimulado: pantalla de prueba con cuentas ficticias (desarrollo
  y demo). Se usa con ENTRA_MODO=simulado.
- ConectorEntraMicrosoft: Microsoft real (OpenID Connect con la librería
  oficial msal). Se usa con ENTRA_MODO=microsoft. Ver CONECTAR_MICROSOFT.md.

Microsoft solo dice QUIÉN es la persona (oid, tenant, correo, nombre). El ROL
lo decide el portal con sus propios datos (usuarios/services.py): Coordinador
si su correo está en COORDINADORES o ya es del grupo Coordinador, Docente si
su correo es el de un Docente registrado, y si no, Estudiante (sin panel).

Configuración (en settings.py o como variables de entorno en .env):

    ENTRA_MODO               "simulado" | "microsoft" | "desactivado".
                             Por defecto "simulado" solo si DEBUG=True.
    ENTRA_TENANT_ID          Directorio(s) (tenant) de la universidad, separados
                             por coma. La U tiene dos: uautonoma.cl
                             (5467f788-2de9-4c6c-bfb4-863594d809cf) y
                             cloud.uautonoma.cl (60dac1b9-6047-489a-a134-b070386cccf7).
                             Solo se aceptan cuentas de esos tenants. Con
                             "organizations" se acepta cualquiera (solo pruebas).
    ENTRA_CLIENT_ID          Id. de la aplicación registrada en Entra ID.
    ENTRA_CLIENT_SECRET      Secreto de esa aplicación (nunca en el repo).
    ENTRA_REDIRECT_URI       Opcional. Por defecto https://<host>/usuarios/auth/callback/
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


_NAMESPACE_OID = uuid.UUID("6f1c7b52-3b0e-4a43-9c55-0a5f6a1d2b10")

_PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


CUENTAS_PRUEBA = (
    {"correo": "coordinador@uautonoma.cl", "nombre": "Coordinador Prueba", "rol": ROL_COORDINADOR},
    {"correo": "docente@uautonoma.cl", "nombre": "Docente Prueba", "rol": ROL_DOCENTE},
    {"correo": "estudiante@uautonoma.cl", "nombre": "Estudiante Prueba", "rol": ROL_ESTUDIANTE},


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


def configuracion_microsoft():
    """Datos de la app registrada en Entra ID; faltan → EntraError explicativo."""
    def valor(nombre):

        return (getattr(settings, nombre, "") or os.getenv(nombre, "") or "").strip().strip("<>\"' ")

    datos = {
        "tenant_id": valor("ENTRA_TENANT_ID"),
        "client_id": valor("ENTRA_CLIENT_ID"),
        "client_secret": valor("ENTRA_CLIENT_SECRET"),
        "redirect_uri": valor("ENTRA_REDIRECT_URI"),
    }
    faltan = [n for n in ("tenant_id", "client_id", "client_secret") if not datos[n]]
    if faltan:
        raise EntraError(
            "El ingreso con Microsoft no está configurado en el servidor "
            f"(faltan: {', '.join('ENTRA_' + n.upper() for n in faltan)}). "
            "Usa el acceso de respaldo o avisa al administrador."
        )
    return datos


class ConectorEntraMicrosoft:
    """
    Microsoft real. Flujo "authorization code" con PKCE, el estándar para apps
    web: el botón manda a Microsoft, Microsoft vuelve a /usuarios/auth/callback/
    con un código y aquí se cambia por el id_token con los datos de la persona.
    """

    SCOPES = ["User.Read"]

    def __init__(self):
        self.config = configuracion_microsoft()

    def _app(self):
        import msal

        return msal.ConfidentialClientApplication(
            self.config["client_id"],
            authority=f"https://login.microsoftonline.com/{self._autoridad()}",
            client_credential=self.config["client_secret"],
        )

    def _tenants(self):
        return [t.strip().lower() for t in self.config["tenant_id"].split(",") if t.strip()]

    def _autoridad(self):
        """Un solo tenant → ese; varios (p. ej. uautonoma.cl y cloud.uautonoma.cl) → "organizations"."""
        tenants = self._tenants()
        return tenants[0] if len(tenants) == 1 else "organizations"

    def iniciar(self, redirect_uri, seleccionar_cuenta=False):
        """Devuelve el "flow" (se guarda en la sesión) con la URL de Microsoft en flow["auth_uri"]."""
        return self._app().initiate_auth_code_flow(
            self.SCOPES,
            redirect_uri=self.config["redirect_uri"] or redirect_uri,
            prompt="select_account" if seleccionar_cuenta else None,
        )

    def completar(self, flow, parametros):
        """Cambia el código que devolvió Microsoft por la identidad de la persona."""
        try:
            resultado = self._app().acquire_token_by_auth_code_flow(flow, dict(parametros.items()))
        except ValueError as exc:
            raise EntraError("El inicio de sesión venció o no es válido. Vuelve a intentarlo.") from exc

        if "error" in resultado:
            detalle = resultado.get("error_description", "").split("\n")[0]
            if "AADSTS65001" in detalle or "consent" in detalle.lower():
                raise EntraError(
                    "La universidad debe aprobar esta aplicación antes de poder usarla "
                    "(consentimiento del administrador de TI)."
                )
            raise EntraError(f"Microsoft rechazó el inicio de sesión: {detalle or resultado['error']}")

        return self.identidad_desde_claims(resultado.get("id_token_claims") or {})

    def identidad_desde_claims(self, claims):
        tenant = (claims.get("tid") or "").lower()
        aceptados = set(self._tenants())
        if not aceptados & {"organizations", "common"} and tenant not in aceptados:
            raise EntraError("Solo se aceptan cuentas de la Universidad Autónoma de Chile.")

        oid = claims.get("oid")
        correo = (claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "").strip().lower()
        if not oid or not _PATRON_CORREO.match(correo):
            raise EntraError("Microsoft no entregó los datos de la cuenta. Vuelve a intentarlo.")

        if correo.rsplit("@", 1)[1] not in dominios_permitidos():
            raise EntraError(f"Solo se permiten cuentas institucionales {texto_dominios()}.")

        nombre = claims.get("given_name") or ""
        apellido = claims.get("family_name") or ""
        if not nombre:
            nombre, _, apellido = (claims.get("name") or correo.split("@", 1)[0]).partition(" ")


        return IdentidadEntra(
            oid=oid, correo=correo, nombre=nombre, apellido=apellido,
            rol=ROL_ESTUDIANTE, tenant_id=tenant,
        )


def correos_coordinadores():
    """Correos que siempre entran como Coordinador (variable COORDINADORES)."""
    valor = getattr(settings, "COORDINADORES", None) or os.getenv("COORDINADORES", "")
    if isinstance(valor, (list, tuple)):
        valor = ",".join(valor)
    return {c.strip().lower() for c in valor.split(",") if c.strip()}


def get_conector():
    ruta = getattr(settings, "ENTRA_CONECTOR", None) or os.getenv("ENTRA_CONECTOR")
    if not ruta:
        ruta = (
            "usuarios.entra.ConectorEntraMicrosoft" if modo() == "microsoft"
            else "usuarios.entra.ConectorEntraSimulado"
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
