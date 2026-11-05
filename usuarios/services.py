"""
Identidades institucionales: una persona = un Usuario.

La universidad entrega dos tipos de cuenta Microsoft (@uautonoma.cl para
funcionarios y @cloud.uautonoma.cl para docentes y estudiantes). Quien tiene
las dos debe ver lo mismo entre con cuál entre. Cada cuenta se guarda como
IdentidadInstitucional y todas apuntan al mismo Usuario.

Toda la lógica de identidades vive aquí; entra.py solo habla con el conector.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from . import entra
from .models import IdentidadInstitucional, Rol


SESION_IDENTIDAD = "identidad_id"
SESION_AVISO_OCULTO = "aviso_vincular_oculto"

# Entre más arriba, más permisos. Al fusionar se conserva el rol más alto.
_PRIORIDAD_ROL = (entra.ROL_COORDINADOR, entra.ROL_DOCENTE, entra.ROL_ESTUDIANTE)

# Bitácoras: quedan como ocurrieron, no se reasignan al fusionar.
_SIN_REASIGNAR = {("auditoria", "auditoriacambio"), ("admin", "logentry")}


class IdentidadError(entra.EntraError):
    """Operación no permitida. El mensaje se puede mostrar al usuario."""


class IdentidadOcupada(IdentidadError):
    """La cuenta ya pertenece a otro Usuario (se puede ofrecer fusionar)."""

    def __init__(self, usuario):
        self.usuario = usuario
        super().__init__("Esa cuenta ya está registrada en el portal como otra persona.")


def normalizar_correo(correo):
    return (correo or "").strip().lower()


# --- Consultas ---------------------------------------------------------------

def identidad_principal(usuario):
    return usuario.identidades.filter(es_principal=True).first()


def correos_de_usuario(usuario):
    """Todos los correos con que la persona puede entrar (en minúsculas)."""
    if usuario is None or not getattr(usuario, "pk", None):
        return set()
    correos = set(usuario.identidades.values_list("correo", flat=True))
    for extra in (usuario.correo_institucional, usuario.email):
        if extra:
            correos.add(normalizar_correo(extra))
    return correos


def usuario_por_correo(correo):
    """Usuario dueño de cualquiera de sus correos vinculados, o None."""
    correo = normalizar_correo(correo)
    if not correo:
        return None
    identidad = (
        IdentidadInstitucional.objects.select_related("usuario")
        .filter(correo=correo)
        .first()
    )
    if identidad:
        return identidad.usuario
    return get_user_model().objects.filter(correo_institucional__iexact=correo).first()


def identidad_actual(request):
    """Cuenta con la que se entró en esta sesión (si no se sabe, la principal)."""
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return None
    identidad_id = request.session.get(SESION_IDENTIDAD)
    if identidad_id:
        identidad = usuario.identidades.filter(pk=identidad_id).first()
        if identidad:
            return identidad
    return identidad_principal(usuario)


def correo_de_sesion(request):
    """Correo de la cuenta usada en esta sesión (con respaldo en el Usuario)."""
    identidad = identidad_actual(request)
    if identidad:
        return identidad.correo
    usuario = request.user
    return normalizar_correo(usuario.correo_institucional or usuario.email)


def oid_de_sesion(request):
    identidad = identidad_actual(request)
    if identidad:
        return identidad.entra_oid
    return request.user.entra_oid or None


def _buscar_identidad(identidad_entra):
    return (
        IdentidadInstitucional.objects.select_related("usuario")
        .filter(tenant_id=identidad_entra.tenant_id, entra_oid=identidad_entra.oid)
        .first()
        or IdentidadInstitucional.objects.select_related("usuario")
        .filter(correo=normalizar_correo(identidad_entra.correo))
        .first()
    )


def _buscar_usuario_antiguo(identidad_entra):
    """Usuarios creados antes de existir las identidades."""
    Usuario = get_user_model()
    return (
        Usuario.objects.filter(entra_oid=identidad_entra.oid).first()
        or Usuario.objects.filter(correo_institucional__iexact=identidad_entra.correo).first()
        or Usuario.objects.filter(username__iexact=identidad_entra.correo).first()
    )


def duenio_de_cuenta(identidad_entra):
    """(usuario, identidad) a quien pertenece la cuenta; (None, None) si es nueva."""
    identidad = _buscar_identidad(identidad_entra)
    if identidad:
        return identidad.usuario, identidad
    return _buscar_usuario_antiguo(identidad_entra), None


# --- Escritura ----------------------------------------------------------------

def sincronizar_principal(usuario):
    """Copia la identidad principal en Usuario.entra_oid / correo_institucional."""
    principal = identidad_principal(usuario)
    if principal is None:
        return
    Usuario = get_user_model()
    ocupado = (
        Usuario.objects.exclude(pk=usuario.pk)
        .filter(Q(correo_institucional__iexact=principal.correo) | Q(entra_oid=principal.entra_oid))
        .exists()
    )
    if ocupado:
        raise IdentidadError(
            "Otra persona del portal tiene registrado ese correo. Contacta a la coordinación."
        )
    if usuario.correo_institucional != principal.correo or usuario.entra_oid != principal.entra_oid:
        usuario.correo_institucional = principal.correo
        usuario.entra_oid = principal.entra_oid
        usuario.save(update_fields=["correo_institucional", "entra_oid"])


def _crear_identidad(usuario, *, correo, oid, tenant_id, origen, ultimo_acceso=None):
    principal = not usuario.identidades.filter(es_principal=True).exists()
    return IdentidadInstitucional.objects.create(
        usuario=usuario,
        correo=normalizar_correo(correo),
        entra_oid=oid,
        tenant_id=tenant_id,
        es_principal=principal,
        origen_vinculo=origen,
        fecha_ultimo_acceso=ultimo_acceso,
    )


def asegurar_identidad_principal(usuario, correo=None, tenant_id=entra.TENANT_SIMULADO):
    """
    Da al usuario su identidad principal si aún no tiene ninguna.
    Lo usan los scripts de datos de prueba. Devuelve la principal o None.
    """
    existente = identidad_principal(usuario)
    if existente:
        return existente
    correo = normalizar_correo(correo or usuario.correo_institucional or usuario.email)
    if not correo or IdentidadInstitucional.objects.filter(correo=correo).exists():
        return None
    oid = usuario.entra_oid or entra.oid_simulado(correo)
    if IdentidadInstitucional.objects.filter(tenant_id=tenant_id, entra_oid=oid).exists():
        return None
    identidad = _crear_identidad(
        usuario, correo=correo, oid=oid, tenant_id=tenant_id,
        origen=IdentidadInstitucional.INICIAL,
    )
    sincronizar_principal(usuario)
    return identidad


def crear_identidades_iniciales(modelo_usuario=None, modelo_identidad=None):
    """
    Una identidad principal INICIAL para cada Usuario con correo que aún no
    tenga ninguna. La usa la migración de datos (con modelos históricos).
    Devuelve cuántas creó.
    """
    Usuario = modelo_usuario or get_user_model()
    Identidad = modelo_identidad or IdentidadInstitucional

    con_identidad = set(Identidad.objects.values_list("usuario_id", flat=True))
    correos_usados = set(Identidad.objects.values_list("correo", flat=True))
    oids_usados = set(
        Identidad.objects.filter(tenant_id=entra.TENANT_SIMULADO).values_list("entra_oid", flat=True)
    )
    creadas = 0
    for usuario in Usuario.objects.exclude(pk__in=con_identidad).order_by("pk"):
        correo = normalizar_correo(usuario.correo_institucional or usuario.email)
        if not correo or correo in correos_usados:
            continue
        oid = usuario.entra_oid or entra.oid_simulado(correo)
        if oid in oids_usados:
            continue
        Identidad.objects.create(
            usuario_id=usuario.pk,
            tenant_id=entra.TENANT_SIMULADO,
            entra_oid=oid,
            correo=correo,
            es_principal=True,
            origen_vinculo="INICIAL",
            fecha_vinculacion=timezone.now(),
            fecha_ultimo_acceso=usuario.fecha_ultimo_acceso,
        )
        correos_usados.add(correo)
        oids_usados.add(oid)
        creadas += 1
    return creadas


def enlazar_docente(usuario):
    """
    Si la persona aún no tiene perfil de Docente, enlaza el Docente registrado
    por Coordinación con cualquiera de sus correos (solo si está libre).
    Nunca le quita el Docente a otro usuario. Devuelve el Docente o None.
    """
    from academico.models import Docente

    docente = Docente.objects.filter(usuario=usuario).first()
    if docente:
        return docente
    correos = correos_de_usuario(usuario)
    if not correos:
        return None
    docente = (
        Docente.objects.annotate(correo_min=Lower("correo_institucional"))
        .filter(usuario__isnull=True, correo_min__in=correos)
        .order_by("pk")
        .first()
    )
    if docente is None:
        return None
    docente.usuario = usuario
    docente.save(update_fields=["usuario"])
    usuario.groups.add(Group.objects.get_or_create(name=entra.ROL_DOCENTE)[0])
    # Quien entró por primera vez con la cuenta cloud quedó como Estudiante.
    usuario.groups.remove(*usuario.groups.filter(name=entra.ROL_ESTUDIANTE))
    if usuario.rol is None or usuario.rol.nombre == entra.ROL_ESTUDIANTE:
        usuario.rol = Rol.objects.get_or_create(nombre=entra.ROL_DOCENTE)[0]
        usuario.save(update_fields=["rol"])
    return docente


@transaction.atomic
def obtener_o_crear_usuario_por_identidad(identidad_entra):
    """
    Usuario local para la cuenta que entrega Entra. Orden de búsqueda:
    identidad (tenant + oid) → identidad por correo → usuario antiguo (y se le
    crea la identidad) → usuario nuevo con identidad principal.
    Devuelve (usuario, identidad).
    """
    Usuario = get_user_model()
    ahora = timezone.now()
    correo = normalizar_correo(identidad_entra.correo)

    usuario, identidad = duenio_de_cuenta(identidad_entra)

    if usuario is None:
        usuario = Usuario(
            username=correo,
            email=correo,
            first_name=identidad_entra.nombre,
            last_name=identidad_entra.apellido,
        )
        usuario.set_unusable_password()

    if usuario.pk and (not usuario.is_active or not usuario.activo):
        raise entra.EntraError("Tu cuenta está desactivada. Contacta a la coordinación.")

    if not usuario.rol_id:
        usuario.rol, _ = Rol.objects.get_or_create(nombre=identidad_entra.rol)
    usuario.fecha_ultimo_acceso = ahora
    usuario.save()

    if identidad is None:
        identidad = _crear_identidad(
            usuario, correo=correo, oid=identidad_entra.oid,
            tenant_id=identidad_entra.tenant_id,
            origen=IdentidadInstitucional.INICIAL, ultimo_acceso=ahora,
        )
    else:
        # Encontrada por correo: se actualiza al oid/tenant que entrega Entra.
        identidad.entra_oid = identidad_entra.oid
        identidad.tenant_id = identidad_entra.tenant_id
        identidad.fecha_ultimo_acceso = ahora
        identidad.save(update_fields=["entra_oid", "tenant_id", "fecha_ultimo_acceso"])

    sincronizar_principal(usuario)

    # El menú lateral y los decoradores trabajan con grupos de Django.
    if not usuario.groups.exists():
        usuario.groups.add(Group.objects.get_or_create(name=identidad_entra.rol)[0])

    enlazar_docente(usuario)
    return usuario, identidad


@transaction.atomic
def vincular_identidad(usuario, identidad_entra, origen, request=None):
    """Agrega a `usuario` una cuenta que aún no es de nadie."""
    duenio, existente = duenio_de_cuenta(identidad_entra)
    if duenio is not None and duenio.pk != usuario.pk:
        raise IdentidadOcupada(duenio)
    if existente is not None:
        return existente

    identidad = _crear_identidad(
        usuario, correo=identidad_entra.correo, oid=identidad_entra.oid,
        tenant_id=identidad_entra.tenant_id, origen=origen,
    )
    sincronizar_principal(usuario)
    enlazar_docente(usuario)
    _auditar(request, usuario, "VINCULAR_CUENTA", None, {"correo": identidad.correo, "origen": origen})
    return identidad


@transaction.atomic
def marcar_principal(usuario, identidad, request=None):
    if identidad.usuario_id != usuario.pk:
        raise IdentidadError("Esa cuenta no es tuya.")
    anterior = identidad_principal(usuario)
    if anterior and anterior.pk == identidad.pk:
        return identidad
    # Primero se quita la anterior: solo puede haber una principal.
    usuario.identidades.filter(es_principal=True).update(es_principal=False)
    identidad.es_principal = True
    identidad.save(update_fields=["es_principal"])
    sincronizar_principal(usuario)
    _auditar(
        request, usuario, "CAMBIAR_CUENTA_PRINCIPAL",
        {"correo": anterior.correo if anterior else None}, {"correo": identidad.correo},
    )
    return identidad


@transaction.atomic
def desvincular_identidad(usuario, identidad, identidad_en_uso=None, request=None):
    if identidad.usuario_id != usuario.pk:
        raise IdentidadError("Esa cuenta no es tuya.")
    if usuario.identidades.count() <= 1:
        raise IdentidadError("No puedes quitar tu única cuenta.")
    if identidad_en_uso and identidad_en_uso.pk == identidad.pk:
        raise IdentidadError("No puedes quitar la cuenta con la que entraste ahora.")

    era_principal = identidad.es_principal
    correo = identidad.correo
    identidad.delete()
    if era_principal:
        nueva = identidad_en_uso or usuario.identidades.order_by("pk").first()
        nueva.es_principal = True
        nueva.save(update_fields=["es_principal"])
        sincronizar_principal(usuario)
    _auditar(request, usuario, "DESVINCULAR_CUENTA", {"correo": correo}, None)


# --- Fusión -------------------------------------------------------------------

def _relaciones_con_usuario():
    """Relaciones (FK, OneToOne, M2M) de otros modelos que apuntan a Usuario."""
    for relacion in get_user_model()._meta.related_objects:
        modelo = relacion.related_model
        if (modelo._meta.app_label, modelo._meta.model_name) in _SIN_REASIGNAR:
            continue
        if modelo is IdentidadInstitucional:
            continue
        yield relacion


def resumen_datos(usuario):
    """[(nombre, cantidad)] de lo que tiene a su nombre (para la confirmación)."""
    resumen = []
    for relacion in _relaciones_con_usuario():
        modelo = relacion.related_model
        if relacion.many_to_many:
            cantidad = getattr(usuario, relacion.get_accessor_name()).count()
        else:
            cantidad = modelo._base_manager.filter(**{relacion.field.name: usuario}).count()
        if cantidad:
            nombre = modelo._meta.verbose_name if cantidad == 1 else modelo._meta.verbose_name_plural
            resumen.append((str(nombre).capitalize(), cantidad))
    return resumen


def _rol_mayor(*roles):
    nombres = {r.nombre: r for r in roles if r is not None}
    for nombre in _PRIORIDAD_ROL:
        if nombre in nombres:
            return nombres[nombre]
    return next(iter(nombres.values()), None)


def comprobar_fusion(origen, destino):
    """Lanza IdentidadError si no se puede fusionar automáticamente."""
    from academico.models import Docente

    if origen.pk == destino.pk:
        raise IdentidadError("Es la misma cuenta.")
    if not origen.is_active or not origen.activo:
        raise IdentidadError("Esa cuenta está desactivada. Contacta a la coordinación.")
    docente_origen = Docente.objects.filter(usuario=origen).first()
    docente_destino = Docente.objects.filter(usuario=destino).first()
    if docente_origen and docente_destino:
        raise IdentidadError(
            "Las dos cuentas tienen un registro de docente distinto "
            f"({docente_destino} y {docente_origen}). Pide a la coordinación que las una."
        )
    for relacion in _relaciones_con_usuario():
        if relacion.one_to_one and relacion.related_model is not Docente:
            filtro = relacion.related_model._base_manager.filter
            if filtro(**{relacion.field.name: origen}).exists() and filtro(**{relacion.field.name: destino}).exists():
                raise IdentidadError("Las dos cuentas tienen datos que no se pueden unir. Contacta a la coordinación.")


@transaction.atomic
def fusionar_usuarios(origen, destino, request=None, cuenta_confirmada=None):
    """
    Pasa todo lo de `origen` a `destino` (misma persona con dos cuentas):
    llaves foráneas, perfil de Docente, grupos e identidades. `origen` queda
    desactivado. Lanza IdentidadError si no se puede.

    `cuenta_confirmada` (IdentidadEntra) es la cuenta de `origen` con la que la
    persona se acaba de autenticar desde "Mi cuenta": queda registrada como
    vinculada por ella.
    """
    comprobar_fusion(origen, destino)

    correos_origen = sorted(correos_de_usuario(origen))
    resumen = resumen_datos(origen)

    for relacion in _relaciones_con_usuario():
        if relacion.many_to_many:
            relacionados = list(getattr(origen, relacion.get_accessor_name()).all())
            getattr(destino, relacion.get_accessor_name()).add(*relacionados)
            getattr(origen, relacion.get_accessor_name()).clear()
        else:
            campo = relacion.field.name
            relacion.related_model._base_manager.filter(**{campo: origen}).update(**{campo: destino})

    # Grupos y permisos: se suman. Si queda con un rol de trabajo, deja de ser Estudiante.
    destino.groups.add(*origen.groups.all())
    destino.user_permissions.add(*origen.user_permissions.all())
    if destino.groups.filter(name__in=[entra.ROL_COORDINADOR, entra.ROL_DOCENTE]).exists():
        destino.groups.remove(*destino.groups.filter(name=entra.ROL_ESTUDIANTE))
    destino.rol = _rol_mayor(destino.rol, origen.rol)
    destino.save(update_fields=["rol"])

    origen.identidades.update(usuario=destino, es_principal=False)

    # El origen se libera de sus datos únicos para que el login no lo vuelva a encontrar.
    username_origen = origen.username
    origen.activo = False
    origen.is_active = False
    origen.correo_institucional = None
    origen.entra_oid = None
    origen.username = f"fusionado-{origen.pk}-{username_origen}"[:150]
    origen.save(update_fields=["activo", "is_active", "correo_institucional", "entra_oid", "username"])

    if cuenta_confirmada is not None:
        identidad = _buscar_identidad(cuenta_confirmada)
        if identidad is None:
            # El origen era un usuario antiguo, sin identidades.
            _crear_identidad(
                destino, correo=cuenta_confirmada.correo, oid=cuenta_confirmada.oid,
                tenant_id=cuenta_confirmada.tenant_id,
                origen=IdentidadInstitucional.CONFIRMADO_USUARIO,
            )
        else:
            identidad.origen_vinculo = IdentidadInstitucional.CONFIRMADO_USUARIO
            identidad.fecha_vinculacion = timezone.now()
            identidad.save(update_fields=["origen_vinculo", "fecha_vinculacion"])

    if not destino.identidades.filter(es_principal=True).exists():
        primera = destino.identidades.order_by("pk").first()
        if primera:
            primera.es_principal = True
            primera.save(update_fields=["es_principal"])
    sincronizar_principal(destino)
    enlazar_docente(destino)

    _auditar(
        request, destino, "FUSIONAR_CUENTAS",
        {"usuario_origen_id": origen.pk, "username": username_origen, "correos": correos_origen},
        {
            "usuario_destino_id": destino.pk,
            "correos": sorted(correos_de_usuario(destino)),
            "datos_movidos": {nombre: cantidad for nombre, cantidad in resumen},
        },
    )
    return destino


def _auditar(request, usuario, accion, anteriores, nuevos):
    from auditoria.services import registrar_auditoria

    registrar_auditoria(
        request=request,
        entidad="Usuario",
        entidad_id=usuario.pk,
        accion=accion,
        valores_anteriores=anteriores,
        valores_nuevos=nuevos,
    )


# --- Aviso en el Inicio -------------------------------------------------------

def aviso_vincular_cuenta(request):
    """
    Texto del aviso "¿También tienes una cuenta…?" para Coordinador y Docente
    que solo tienen cuentas de uno de los dos dominios. None si no corresponde.
    """
    from .permissions import es_coordinador, es_docente

    usuario = request.user
    if not usuario.is_authenticated or request.session.get(SESION_AVISO_OCULTO):
        return None
    if not (es_coordinador(usuario) or es_docente(usuario)):
        return None

    permitidos = entra.dominios_permitidos()
    dominios = {c.rsplit("@", 1)[-1] for c in correos_de_usuario(usuario) if "@" in c}
    dominios &= set(permitidos)
    if len(dominios) != 1 or len(permitidos) < 2:
        return None
    otro = next(d for d in permitidos if d not in dominios)
    return (
        f"¿También tienes una cuenta @{otro}? Vincúlala para ver todo en un solo "
        "lugar y no preocuparte de con qué correo entras."
    )
