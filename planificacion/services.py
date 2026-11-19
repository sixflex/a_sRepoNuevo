"""
Revisión de la planificación que envía Dirección de Carrera (HU-01, HU-12).

Flujo: Dirección envía la planilla -> se revisa cada fila (solo errores
reales, RF-ACA-04: obligatorios, formato y NRC duplicado) -> el Coordinador
corrige filas, aprueba o devuelve. Recién al aprobar se crean la asignatura
y el docente que todavía no existan, la sección y la Ruta A+S.
"""
import difflib
import unicodedata
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from academico.constantes import SECCION_ACTIVA
from academico.models import (Asignatura,AsignaturaCarrera,Campus,Carrera,Docente,Seccion,SeccionCarrera,SeccionDocente,)
from .models import (FilaPlanificacion,PlanificacionError,)
from rutas.services import asignar_ruta_as_si_corresponde
from core.validators import normalizar_rut, validar_rut_chileno

# Estado de cada fila. PENDIENTE = sin errores, espera la aprobación del Coordinador.
ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_ACEPTADA = "ACEPTADA"
ESTADO_OBSERVADA = "OBSERVADA"

# Estado de la planificación (texto, sin migración). FINAL es el valor que ya
# se guardaba al enviar la versión final: ahora significa "por revisar".
PLAN_BORRADOR = "BORRADOR"
PLAN_ENVIADA = "FINAL"
PLAN_APROBADA = "APROBADA"
PLAN_DEVUELTA = "DEVUELTA"
# Dirección puede editar el enlace mientras está en borrador o devuelta.
PLAN_EDITABLES = (PLAN_BORRADOR, PLAN_DEVUELTA)

# Días que se reabre un enlace vencido al devolver la planificación.
DIAS_REAPERTURA = 7


def clave_nombre(texto):
    """Para comparar nombres sin mayúsculas, tildes ni espacios extra."""
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(texto.casefold().split())

def _texto(valor):
    return (valor or "").strip()

def _registrar_error(fila, campo, codigo, mensaje):
    PlanificacionError.objects.create(
        fila=fila,
        campo=campo,
        codigo=codigo,
        mensaje=mensaje,
    )

def facultad_de_enlace(enlace):
    """
    Facultad de la unidad académica del enlace (la de la unidad o la de su
    carrera). Queda fija en la planilla y limita las carreras que se ofrecen.
    """
    unidad = enlace.unidad_academica
    if unidad.facultad_id:
        return unidad.facultad
    if unidad.carrera_id:
        return unidad.carrera.facultad
    return None


def campus_de_unidad(unidad):
    """
    Campus donde opera una unidad según la oferta académica (CarreraCampus):
    unidad de una carrera -> los campus de esa carrera; unidad de facultad ->
    los de todas sus carreras activas.
    """
    if unidad.carrera_id:
        return Campus.objects.filter(carreras=unidad.carrera).distinct()
    if unidad.facultad_id:
        return Campus.objects.filter(
            carreras__facultad_id=unidad.facultad_id,
            carreras__activo=True,
        ).distinct()
    return Campus.objects.none()


def _resolver_carrera(fila):
    nombre = _texto(fila.carrera_texto)

    if not nombre:
        _registrar_error(
            fila,
            "carrera",
            "CAMPO_OBLIGATORIO",
            "Debe indicar una carrera.",
        )
        return None

    carrera = (
        Carrera.objects
        .filter(nombre__iexact=nombre, activo=True)
        .first()
    )

    if carrera is None:
        _registrar_error(
            fila,
            "carrera",
            "CARRERA_NO_ENCONTRADA",
            f'No existe una carrera activa con el nombre "{nombre}".',
        )
        return None

    facultad = facultad_de_enlace(fila.planificacion.enlace)
    if facultad is not None and carrera.facultad_id != facultad.id:
        _registrar_error(
            fila,
            "carrera",
            "CARRERA_FUERA_DE_FACULTAD",
            f'La carrera "{carrera.nombre}" no pertenece a {facultad.nombre}, la facultad de este enlace.',
        )
        return None

    campus = fila.planificacion.enlace.campus
    if not carrera.campus.filter(pk=campus.pk).exists():
        _registrar_error(
            fila,
            "carrera",
            "CARRERA_NO_IMPARTIDA_EN_CAMPUS",
            (
                f'La carrera "{carrera.nombre}" no está registrada en {campus.nombre}. '
                "Si se dicta ahí, agregue el campus en Gestión académica > Carreras."
            ),
        )
        return None

    return carrera

def _asignaturas_activas(carrera=None):
    asignaturas = Asignatura.objects.filter(activo=True)
    if carrera is not None:
        asignaturas = asignaturas.filter(carreras=carrera)
    return list(asignaturas.distinct().order_by("nombre"))


def buscar_asignatura(nombre, carrera):
    """
    Asignatura ya registrada con ese nombre o código (sin distinguir tildes ni
    mayúsculas). Primero en la carrera; si no, en otra carrera (al aprobar se
    asocia también a esta). None si es nueva.
    """
    buscado = clave_nombre(nombre)
    if not buscado:
        return None
    for grupo in (_asignaturas_activas(carrera), _asignaturas_activas()):
        for asignatura in grupo:
            if buscado in (clave_nombre(asignatura.nombre), clave_nombre(asignatura.codigo)):
                return asignatura
    return None


def asignaturas_parecidas(nombre, carrera, limite=3):
    """
    Asignaturas de la carrera con un nombre parecido (ej. «Consultoria» y
    «Consultoría de Empresas»), para que el Coordinador vincule en vez de
    crear una duplicada.
    """
    buscado = clave_nombre(nombre)
    if not buscado or carrera is None:
        return []
    parecidas = []
    for asignatura in _asignaturas_activas(carrera):
        clave = clave_nombre(asignatura.nombre)
        if clave == buscado:
            continue
        similitud = difflib.SequenceMatcher(None, buscado, clave).ratio()
        if buscado in clave or clave in buscado or similitud >= 0.6:
            parecidas.append((similitud, asignatura))
    parecidas.sort(key=lambda par: -par[0])
    return [asignatura for _, asignatura in parecidas[:limite]]


def _resolver_asignatura(fila, carrera):
    """
    La asignatura la informa Dirección: si no existe no es un error, se crea
    al aprobar. Solo se exige que venga escrita.
    """
    nombre = _texto(fila.asignatura_texto)

    if not nombre:
        _registrar_error(
            fila,
            "asignatura",
            "CAMPO_OBLIGATORIO",
            "Debe indicar una asignatura.",
        )
        return False, None

    return True, buscar_asignatura(nombre, carrera)

def _validar_campos_basicos(fila):
    valido = True

    if not _texto(fila.nrc):
        _registrar_error(
            fila,
            "nrc",
            "CAMPO_OBLIGATORIO",
            "Debe indicar el NRC.",
        )
        valido = False

    if not _texto(fila.seccion):
        _registrar_error(
            fila,
            "seccion",
            "CAMPO_OBLIGATORIO",
            "Debe indicar la sección.",
        )
        valido = False

    if (
        fila.estudiantes_planificados is not None
        and fila.estudiantes_planificados < 0
    ):
        _registrar_error(
            fila,
            "estudiantes_planificados",
            "VALOR_INVALIDO",
            "La cantidad de estudiantes no puede ser negativa.",
        )
        valido = False

    return valido

def _validar_nrc(fila):
    periodo = fila.planificacion.enlace.periodo
    nrc = _texto(fila.nrc)

    if not nrc:
        return False

    existente = Seccion.objects.filter(
        periodo=periodo,
        nrc__iexact=nrc,
    ).first()

    if existente is not None:
        _registrar_error(
            fila,
            "nrc",
            "NRC_DUPLICADO",
            (
                f'El NRC "{nrc}" ya se encuentra registrado '
                f"para el período {periodo.nombre}."
            ),
        )
        return False

    # El mismo NRC en una fila anterior de esta planificación.
    anterior = (
        fila.planificacion.filas
        .filter(nrc__iexact=nrc, numero_fila__lt=fila.numero_fila)
        .exclude(pk=fila.pk)
        .order_by("numero_fila")
        .first()
    )
    if anterior is not None:
        _registrar_error(
            fila,
            "nrc",
            "NRC_DUPLICADO",
            f'El NRC "{nrc}" se repite en la fila {anterior.numero_fila} de esta planificación.',
        )
        return False

    return True

def _resolver_docente(docente_fila):

    rut = _texto(docente_fila.rut)
    correo = _texto(docente_fila.correo)

    docente = None

    if rut:
        # El RUT se compara normalizado (sin puntos, con guion), igual que
        # se guarda en Gestión académica; se mantiene el texto original
        # por si quedan docentes antiguos guardados con otro formato.
        docente = Docente.objects.filter(
            Q(rut__iexact=normalizar_rut(rut)) | Q(rut__iexact=rut)
        ).first()

    if docente is None and correo:
        docente = Docente.objects.filter(
            correo_institucional__iexact=correo
        ).first()

    if docente is None and correo:
        # La persona puede tener dos cuentas (@uautonoma.cl y @cloud.uautonoma.cl):
        # se busca al docente registrado con cualquiera de sus correos vinculados.
        from usuarios.services import correos_de_usuario, usuario_por_correo

        usuario = usuario_por_correo(correo)
        if usuario is not None:
            docente = Docente.objects.filter(usuario=usuario).first()
            if docente is None:
                docente = (
                    Docente.objects.filter(usuario__isnull=True)
                    .filter(_q_correos(correos_de_usuario(usuario)))
                    .first()
                )

    return docente


def _q_correos(correos):
    filtro = Q(pk__in=[])
    for correo in correos:
        filtro |= Q(correo_institucional__iexact=correo)
    return filtro

def separar_nombre(nombre):
    """
    «Juan Pérez Soto» -> ('Juan', 'Pérez Soto'). Los dos últimos apellidos
    con 3 o más palabras; con 2 palabras, la última. Se puede corregir
    después en Gestión académica > Docentes.
    """
    palabras = (nombre or "").split()
    if len(palabras) < 2:
        return " ".join(palabras), ""
    corte = len(palabras) - 2 if len(palabras) >= 3 else 1
    return " ".join(palabras[:corte]), " ".join(palabras[corte:])


def faltantes_docente_nuevo(docente_fila):
    """Lo que falta para poder registrar a un docente que aún no existe."""
    faltan = []
    if not _texto(docente_fila.rut):
        faltan.append("el RUT")
    else:
        try:
            validar_rut_chileno(docente_fila.rut)
        except ValidationError:
            faltan.append("un RUT válido")
    nombres, apellidos = separar_nombre(docente_fila.nombre)
    if not nombres or not apellidos:
        faltan.append("nombre y apellido")
    correo = _texto(docente_fila.correo)
    if not correo:
        faltan.append("el correo")
    else:
        try:
            validate_email(correo)
        except ValidationError:
            faltan.append("un correo válido")
        else:
            if Docente.objects.filter(correo_institucional__iexact=correo).exists():
                faltan.append("un correo que no use otro docente")
    return faltan


def _validar_docentes(fila):
    """
    Un docente que no está registrado no es un error: se registra al aprobar
    con los datos que mandó Dirección. Solo se observa si faltan datos para
    poder registrarlo.
    """
    docentes_fila = list(fila.docentes.all())

    if not docentes_fila:
        _registrar_error(
            fila,
            "docente",
            "DOCENTE_OBLIGATORIO",
            "La fila debe contener al menos un docente.",
        )
        return False

    valido = True

    for docente_fila in docentes_fila:
        docente = _resolver_docente(docente_fila)

        if docente is not None:
            docente_fila.docente_resuelto = docente
            docente_fila.save(update_fields=["docente_resuelto"])
            continue

        faltan = faltantes_docente_nuevo(docente_fila)
        if faltan:
            _registrar_error(
                fila,
                "docente",
                "DOCENTE_NUEVO_INCOMPLETO",
                (
                    f'"{docente_fila.nombre or "Sin nombre"}" no está registrado como docente. '
                    f"Para registrarlo falta {', '.join(faltan)}."
                ),
            )
            valido = False

    return valido


def validar_fila(fila):
    fila.errores.all().delete()

    fila.campus_resuelto = None
    fila.carrera_resuelta = None
    fila.asignatura_resuelta = None
    fila.seccion_resultante = None

    fila.docentes.update(docente_resuelto=None)

    valido = _validar_campos_basicos(fila)

    enlace = fila.planificacion.enlace

    campus = enlace.campus

    if campus is None or not campus.activo:
        _registrar_error(
            fila,
            "campus",
            "CAMPUS_INVALIDO",
            "El campus asociado al enlace no se encuentra activo.",
        )
        valido = False
    else:
        fila.campus_resuelto = campus

    carrera = _resolver_carrera(fila)

    if carrera is None:
        valido = False
    else:
        fila.carrera_resuelta = carrera

    asignatura_informada, asignatura = _resolver_asignatura(fila, carrera)

    if not asignatura_informada:
        valido = False
    fila.asignatura_resuelta = asignatura

    if not _validar_nrc(fila):
        valido = False

    if not _validar_docentes(fila):
        valido = False

    # Sin errores la fila queda lista para que el Coordinador la apruebe.
    fila.estado_validacion = (
        ESTADO_PENDIENTE
        if valido
        else ESTADO_OBSERVADA
    )

    fila.save(
        update_fields=[
            "campus_resuelto",
            "carrera_resuelta",
            "asignatura_resuelta",
            "seccion_resultante",
            "estado_validacion",
        ]
    )

    return valido

def _asignatura_para_aprobar(fila):
    """Usa la asignatura registrada (asociándola a la carrera) o la crea."""
    asignatura = buscar_asignatura(fila.asignatura_texto, fila.carrera_resuelta)
    creada = False
    if asignatura is None:
        # El código de asignatura es institucional: no se inventa, el
        # Coordinador lo puede agregar después en Gestión académica.
        asignatura = Asignatura.objects.create(
            nombre=" ".join(_texto(fila.asignatura_texto).split()),
            codigo=None,
            activo=True,
        )
        creada = True
    AsignaturaCarrera.objects.get_or_create(
        asignatura=asignatura,
        carrera=fila.carrera_resuelta,
    )
    return asignatura, creada


def _docente_para_aprobar(docente_fila):
    """Docente registrado (por RUT o correo) o uno nuevo con los datos de Dirección."""
    docente = _resolver_docente(docente_fila)
    if docente is not None:
        return docente, False
    nombres, apellidos = separar_nombre(docente_fila.nombre)
    docente = Docente.objects.create(
        rut=validar_rut_chileno(docente_fila.rut),
        nombres=nombres,
        apellidos=apellidos,
        correo_institucional=_texto(docente_fila.correo).lower(),
        telefono=_texto(docente_fila.telefono) or None,
        activo=True,
    )
    return docente, True


def consolidar_fila(fila, creados=None):
    """
    Crea la sección de una fila aprobada. Si la asignatura o el docente no
    existen se registran aquí. `creados` junta lo nuevo para la auditoría.
    """
    if fila.estado_validacion != ESTADO_PENDIENTE or fila.seccion_resultante_id:
        return None

    creados = creados if creados is not None else {"asignaturas": [], "docentes": []}
    planificacion = fila.planificacion
    enlace = planificacion.enlace

    asignatura, asignatura_creada = _asignatura_para_aprobar(fila)
    if asignatura_creada:
        creados["asignaturas"].append(asignatura.nombre)
    fila.asignatura_resuelta = asignatura

    seccion = Seccion.objects.create(
        periodo=enlace.periodo,
        campus=fila.campus_resuelto,
        asignatura=asignatura,
        nrc=_texto(fila.nrc),
        seccion=_texto(fila.seccion),
        jornada=_texto(fila.jornada) or None,
        horario=_texto(fila.horario) or None,
        estado=SECCION_ACTIVA,
        fecha_consolidacion=timezone.now(),
    )

    SeccionCarrera.objects.create(
        seccion=seccion,
        carrera=fila.carrera_resuelta,
        nivel=_texto(fila.nivel) or None,
        declaracion_as=fila.declaracion_as,
        estudiantes_planificados=fila.estudiantes_planificados,
    )

    for docente_fila in fila.docentes.all():
        docente, docente_creado = _docente_para_aprobar(docente_fila)
        if docente_creado:
            creados["docentes"].append(f"{docente.nombres} {docente.apellidos} ({docente.rut})")
        docente_fila.docente_resuelto = docente
        docente_fila.save(update_fields=["docente_resuelto"])

        SeccionDocente.objects.get_or_create(
            seccion=seccion,
            docente=docente,
            defaults={
                "tipo_contrato": (
                    _texto(docente_fila.tipo_contrato)
                    or None
                ),
                "capacitado_as": docente_fila.capacitado_as,
            },
        )

    fila.seccion_resultante = seccion
    fila.estado_validacion = ESTADO_ACEPTADA
    fila.save(update_fields=["seccion_resultante", "asignatura_resuelta", "estado_validacion"])
    asignar_ruta_as_si_corresponde(seccion)

    return seccion


def actualizar_totales(planificacion):
    filas = planificacion.filas
    planificacion.filas_recibidas = filas.count()
    planificacion.filas_aceptadas = filas.filter(estado_validacion=ESTADO_ACEPTADA).count()
    planificacion.filas_observadas = filas.filter(estado_validacion=ESTADO_OBSERVADA).count()
    planificacion.save(update_fields=["filas_recibidas", "filas_aceptadas", "filas_observadas"])


@transaction.atomic
def revisar_planificacion(planificacion):
    """
    Al recibir la versión final: valida cada fila sin crear nada. Las filas
    ya incorporadas antes (tienen sección) no se vuelven a revisar.
    """
    for fila in planificacion.filas.filter(seccion_resultante__isnull=True):
        validar_fila(fila)
    actualizar_totales(planificacion)
    return planificacion


def revision_fila(fila):
    """
    Lo que el Coordinador ve de cada fila antes de aprobar: si la asignatura
    y cada docente ya existen o se crearán, y asignaturas parecidas.
    """
    if fila.seccion_resultante_id:
        return {"incorporada": True}
    carrera = fila.carrera_resuelta
    asignatura = buscar_asignatura(fila.asignatura_texto, carrera) if _texto(fila.asignatura_texto) else None
    if asignatura is None:
        estado_asignatura = "nueva"
    elif carrera is not None and not asignatura.carreras.filter(pk=carrera.pk).exists():
        estado_asignatura = "otra_carrera"
    else:
        estado_asignatura = "registrada"
    return {
        "incorporada": False,
        "asignatura": asignatura,
        "estado_asignatura": estado_asignatura,
        "parecidas": asignaturas_parecidas(fila.asignatura_texto, carrera) if asignatura is None else [],
        "docentes": [
            {"fila": docente_fila, "docente": _resolver_docente(docente_fila)}
            for docente_fila in fila.docentes.all()
        ],
    }


class PlanificacionNoAprobable(Exception):
    pass


def aprobar_planificacion(planificacion, request=None):
    """
    El Coordinador aprueba: se crean asignaturas y docentes nuevos, las
    secciones y la Ruta A+S. Si alguna fila queda observada no se aprueba
    nada, para que corrija la fila o devuelva la planificación.
    """
    if planificacion.estado != PLAN_ENVIADA:
        raise PlanificacionNoAprobable("Solo se puede aprobar una planificación enviada y por revisar.")

    revisar_planificacion(planificacion)
    if planificacion.filas_observadas:
        raise PlanificacionNoAprobable(
            f"Hay {planificacion.filas_observadas} fila(s) observada(s). "
            "Corríjalas con «Editar» o devuelva la planificación a Dirección."
        )

    # La revisión queda guardada aunque no se apruebe (filas observadas);
    # lo que se crea al aprobar va todo o nada.
    with transaction.atomic():
        return _incorporar_planificacion(planificacion, request)


def _incorporar_planificacion(planificacion, request):
    creados = {"asignaturas": [], "docentes": []}
    secciones = 0
    for fila in (
        planificacion.filas
        .filter(estado_validacion=ESTADO_PENDIENTE, seccion_resultante__isnull=True)
        .select_related("planificacion__enlace__periodo", "campus_resuelto", "carrera_resuelta")
        .order_by("numero_fila", "id")
    ):
        try:
            with transaction.atomic():
                if consolidar_fila(fila, creados):
                    secciones += 1
        except IntegrityError:
            # Otro proceso creó el mismo NRC entre la revisión y la aprobación.
            raise PlanificacionNoAprobable(
                f"No fue posible incorporar la fila {fila.numero_fila}: "
                "sus datos chocan con una sección ya registrada. Revise el NRC."
            )

    planificacion.estado = PLAN_APROBADA
    planificacion.save(update_fields=["estado"])
    actualizar_totales(planificacion)

    from auditoria.services import registrar_auditoria
    registrar_auditoria(
        request=request,
        entidad="Planificacion",
        entidad_id=planificacion.id,
        accion="APROBAR_PLANIFICACION",
        valores_anteriores={"estado": PLAN_ENVIADA},
        valores_nuevos={
            "estado": PLAN_APROBADA,
            "secciones_creadas": secciones,
            "asignaturas_creadas": creados["asignaturas"],
            "docentes_creados": creados["docentes"],
        },
    )
    return secciones, creados


@transaction.atomic
def devolver_planificacion(planificacion, motivo, request=None):
    """
    Devuelve la planificación a Dirección para que la corrija y la vuelva a
    enviar: el enlace se reabre (si venció, por DIAS_REAPERTURA días más).
    El correo con el motivo lo envía la vista.
    """
    if planificacion.estado != PLAN_ENVIADA:
        raise PlanificacionNoAprobable("Solo se puede devolver una planificación enviada y por revisar.")

    enlace = planificacion.enlace
    anteriores = {
        "estado": planificacion.estado,
        "enlace_activo": enlace.activo,
        "fecha_expiracion": enlace.fecha_expiracion.isoformat() if enlace.fecha_expiracion else None,
    }

    minimo = timezone.now() + timedelta(days=DIAS_REAPERTURA)
    enlace.activo = True
    if enlace.fecha_expiracion is not None and enlace.fecha_expiracion < minimo:
        enlace.fecha_expiracion = minimo
    enlace.save(update_fields=["activo", "fecha_expiracion"])

    planificacion.estado = PLAN_DEVUELTA
    planificacion.save(update_fields=["estado"])

    from auditoria.services import registrar_auditoria
    registrar_auditoria(
        request=request,
        entidad="Planificacion",
        entidad_id=planificacion.id,
        accion="DEVOLVER_PLANIFICACION",
        valores_anteriores=anteriores,
        valores_nuevos={
            "estado": PLAN_DEVUELTA,
            "motivo": motivo,
            "fecha_expiracion": enlace.fecha_expiracion.isoformat() if enlace.fecha_expiracion else None,
        },
    )
    return planificacion


def motivo_devolucion(planificacion):
    """Último motivo con que el Coordinador devolvió la planificación (queda en auditoría)."""
    from auditoria.models import AuditoriaCambio
    registro = (
        AuditoriaCambio.objects
        .filter(entidad="Planificacion", entidad_id=str(planificacion.pk), accion="DEVOLVER_PLANIFICACION")
        .order_by("-fecha", "-id")
        .first()
    )
    return (registro.valores_nuevos_json or {}).get("motivo", "") if registro else ""


def opciones_asignaturas():
    """
    {carrera: [asignaturas]} de las asignaturas ya registradas por carrera,
    para sugerirlas al escribir (sin obligar a elegir de una lista enorme).
    """
    opciones = {}
    for nombre_carrera, nombre_asignatura in (
        AsignaturaCarrera.objects
        .filter(carrera__activo=True, asignatura__activo=True)
        .order_by("asignatura__nombre")
        .values_list("carrera__nombre", "asignatura__nombre")
    ):
        opciones.setdefault(nombre_carrera, []).append(nombre_asignatura)
    return opciones
