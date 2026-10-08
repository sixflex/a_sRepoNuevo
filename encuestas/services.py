"""
Lógica del módulo de formularios configurables (HU-09, CDE-100 a CDE-106).

Formato de una regla de visibilidad (BloqueFormulario.regla_visibilidad_json,
PreguntaFormulario.regla_visibilidad_json y cada entrada de
configuracion_json["visibilidad_opciones"]):

    {"pregunta": <id de PreguntaFormulario>, "valores": ["VALOR_1", "VALOR_2"]}

Se cumple cuando la pregunta referida está visible y la persona eligió
alguno de esos valores. Una regla vacía (None) siempre se cumple.
"""

import copy
import re
import uuid
from collections import Counter
from datetime import datetime, time

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify

from . import constantes as c
from .models import (
    BloqueFormulario,
    EnlaceFormulario,
    FormularioPlantilla,
    FormularioVersion,
    OpcionPregunta,
    PreguntaFormulario,
    RespuestaArchivo,
    RespuestaFormulario,
    RespuestaOpcion,
    RespuestaPregunta,
)


class FormularioNoEditable(Exception):
    """La versión ya tiene respuestas o no está en un estado editable (RN-17)."""


class TransicionInvalida(Exception):
    """El cambio de estado pedido no corresponde al estado actual."""


# ---------------------------------------------------------------------------
# Estructura y visibilidad
# ---------------------------------------------------------------------------

def cargar_estructura(version):
    """Devuelve (bloques, preguntas) de la versión, ya ordenados."""
    bloques = list(version.bloques.order_by("orden", "id"))
    orden_bloque = {b.id: i for i, b in enumerate(bloques)}
    preguntas = list(
        version.preguntas.select_related("bloque").prefetch_related("opciones")
    )
    preguntas.sort(key=lambda p: (orden_bloque.get(p.bloque_id, -1), p.orden, p.id))
    return bloques, preguntas


def opciones_ordenadas(pregunta):
    return sorted(pregunta.opciones.all(), key=lambda o: (o.orden, o.id))


def configuracion(pregunta):
    return pregunta.configuracion_json or {}


def _cumple(regla, seleccion, preguntas_visibles):
    if not regla:
        return True
    pregunta_id = regla.get("pregunta")
    valores = set(regla.get("valores") or [])
    if pregunta_id not in preguntas_visibles:
        return False
    return bool(valores & seleccion.get(pregunta_id, set()))


def calcular_visibilidad(bloques, preguntas, seleccion):
    """
    Calcula qué se muestra según lo elegido (RF-FOR-03).

    `seleccion` es {pregunta_id: {valores elegidos}}. Las reglas solo pueden
    apuntar a preguntas anteriores, así que basta un recorrido en orden.
    Devuelve (bloques_visibles, preguntas_visibles, opciones_visibles) donde
    opciones_visibles es {pregunta_id: [OpcionPregunta, ...]}.
    """
    preguntas_por_bloque = {}
    for pregunta in preguntas:
        preguntas_por_bloque.setdefault(pregunta.bloque_id, []).append(pregunta)

    bloques_visibles = set()
    preguntas_visibles = set()
    opciones_visibles = {}

    def procesar(pregunta, bloque_visible):
        if not bloque_visible:
            return
        if not _cumple(pregunta.regla_visibilidad_json, seleccion, preguntas_visibles):
            return
        preguntas_visibles.add(pregunta.id)
        reglas_opciones = configuracion(pregunta).get("visibilidad_opciones") or {}
        opciones_visibles[pregunta.id] = [
            opcion
            for opcion in opciones_ordenadas(pregunta)
            if _cumple(reglas_opciones.get(opcion.valor), seleccion, preguntas_visibles)
        ]

    for pregunta in preguntas_por_bloque.get(None, []):
        procesar(pregunta, True)

    for bloque in bloques:
        visible = _cumple(bloque.regla_visibilidad_json, seleccion, preguntas_visibles)
        if visible:
            bloques_visibles.add(bloque.id)
        for pregunta in preguntas_por_bloque.get(bloque.id, []):
            procesar(pregunta, visible)

    return bloques_visibles, preguntas_visibles, opciones_visibles


def seleccion_desde_datos(preguntas, datos):
    """Lee de un QueryDict los valores elegidos en preguntas con opciones."""
    seleccion = {}
    for pregunta in preguntas:
        if pregunta.tipo not in c.TIPOS_CON_OPCIONES:
            continue
        validos = {o.valor for o in pregunta.opciones.all()}
        elegidos = set(datos.getlist(nombre_campo(pregunta))) if datos else set()
        seleccion[pregunta.id] = elegidos & validos
    return seleccion


def nombre_campo(pregunta):
    return f"p{pregunta.id}"


def nombre_campo_otro(pregunta):
    return f"p{pregunta.id}_otro"


def preguntas_condicionantes(version, antes_de=None):
    """
    Preguntas que pueden usarse como condición: de respuesta única con opciones
    y ubicadas antes del elemento que se está configurando.
    """
    _, preguntas = cargar_estructura(version)
    resultado = []
    for pregunta in preguntas:
        if antes_de is not None and pregunta.id == antes_de.id:
            break
        if pregunta.tipo in c.TIPOS_CONDICIONANTES:
            resultado.append(pregunta)
    return resultado


def pregunta_selector(preguntas):
    return next((p for p in preguntas if p.tipo == c.SELECTOR_PROGRAMA), None)


# ---------------------------------------------------------------------------
# Estados y edición (CDE-100, CDE-105)
# ---------------------------------------------------------------------------

def tiene_respuestas(version):
    return version.respuestas.exists()


def es_editable(version):
    return version.estado in (c.BORRADOR, c.PUBLICADA) and not tiene_respuestas(version)


def asegurar_editable(version):
    if not es_editable(version):
        raise FormularioNoEditable(
            "Esta versión ya tiene respuestas o está cerrada. "
            "Crea una nueva versión para modificarla."
        )


def _codigo_unico(titulo):
    base = slugify(titulo).upper().replace("-", "_")[:48] or "FORMULARIO"
    codigo = base
    sufijo = 2
    while FormularioPlantilla.objects.filter(codigo=codigo).exists():
        codigo = f"{base}_{sufijo}"
        sufijo += 1
    return codigo


@transaction.atomic
def crear_formulario(titulo, usuario=None, descripcion="", proceso="GENERAL", contexto_tipo=""):
    plantilla = FormularioPlantilla.objects.create(
        codigo=_codigo_unico(titulo),
        titulo=titulo,
        descripcion=descripcion or None,
        proceso=proceso or "GENERAL",
        activo=True,
    )
    version = FormularioVersion.objects.create(
        plantilla=plantilla,
        creado_por_usuario=usuario,
        numero_version=1,
        estado=c.BORRADOR,
        contexto_tipo=contexto_tipo or None,
        fecha_creacion=timezone.now(),
    )
    BloqueFormulario.objects.create(formulario_version=version, titulo="Sección 1", orden=1)
    return version


def _remapear_regla(regla, mapa_preguntas):
    if not regla or regla.get("pregunta") not in mapa_preguntas:
        return None
    nueva = dict(regla)
    nueva["pregunta"] = mapa_preguntas[regla["pregunta"]]
    return nueva


def _copiar_contenido(origen, destino):
    """Copia bloques, preguntas, opciones y reglas, reasignando los ids."""
    mapa_bloques = {}
    for bloque in origen.bloques.order_by("orden", "id"):
        mapa_bloques[bloque.id] = BloqueFormulario.objects.create(
            formulario_version=destino,
            titulo=bloque.titulo,
            descripcion=bloque.descripcion,
            orden=bloque.orden,
            regla_visibilidad_json=copy.deepcopy(bloque.regla_visibilidad_json),
        )

    mapa_preguntas = {}
    nuevas_preguntas = []
    for pregunta in origen.preguntas.order_by("id").prefetch_related("opciones"):
        nueva = PreguntaFormulario.objects.create(
            version=destino,
            bloque=mapa_bloques.get(pregunta.bloque_id),
            texto=pregunta.texto,
            tipo=pregunta.tipo,
            obligatoria=pregunta.obligatoria,
            orden=pregunta.orden,
            configuracion_json=copy.deepcopy(pregunta.configuracion_json),
            regla_visibilidad_json=copy.deepcopy(pregunta.regla_visibilidad_json),
        )
        mapa_preguntas[pregunta.id] = nueva.id
        nuevas_preguntas.append((pregunta, nueva))
        OpcionPregunta.objects.bulk_create([
            OpcionPregunta(
                pregunta=nueva,
                texto=opcion.texto,
                valor=opcion.valor,
                orden=opcion.orden,
                es_otras=opcion.es_otras,
            )
            for opcion in pregunta.opciones.all()
        ])

    for bloque in mapa_bloques.values():
        if bloque.regla_visibilidad_json:
            bloque.regla_visibilidad_json = _remapear_regla(bloque.regla_visibilidad_json, mapa_preguntas)
            bloque.save(update_fields=["regla_visibilidad_json"])

    for original, nueva in nuevas_preguntas:
        nueva.regla_visibilidad_json = _remapear_regla(nueva.regla_visibilidad_json, mapa_preguntas)
        if original.pregunta_padre_id in mapa_preguntas:
            nueva.pregunta_padre_id = mapa_preguntas[original.pregunta_padre_id]
        config = nueva.configuracion_json or {}
        if config.get("visibilidad_opciones"):
            config["visibilidad_opciones"] = {
                valor: _remapear_regla(regla, mapa_preguntas)
                for valor, regla in config["visibilidad_opciones"].items()
            }
            nueva.configuracion_json = config
        nueva.save(update_fields=["regla_visibilidad_json", "pregunta_padre", "configuracion_json"])


@transaction.atomic
def crear_nueva_version(version, usuario=None):
    """Crea la versión siguiente en borrador con el mismo contenido (RN-17)."""
    numero = (
        version.plantilla.versiones.aggregate(m=Max("numero_version"))["m"] or 0
    ) + 1
    nueva = FormularioVersion.objects.create(
        plantilla=version.plantilla,
        creado_por_usuario=usuario,
        numero_version=numero,
        estado=c.BORRADOR,
        contexto_tipo=version.contexto_tipo,
        fecha_creacion=timezone.now(),
    )
    _copiar_contenido(version, nueva)
    return nueva


@transaction.atomic
def copiar_formulario(version, usuario=None, titulo=None):
    """Duplica el formulario completo como uno nuevo, en borrador."""
    plantilla = version.plantilla
    titulo = titulo or f"Copia de {plantilla.titulo}"
    nueva_plantilla = FormularioPlantilla.objects.create(
        codigo=_codigo_unico(titulo),
        titulo=titulo,
        descripcion=plantilla.descripcion,
        proceso=plantilla.proceso,
        activo=True,
    )
    nueva = FormularioVersion.objects.create(
        plantilla=nueva_plantilla,
        creado_por_usuario=usuario,
        numero_version=1,
        estado=c.BORRADOR,
        contexto_tipo=version.contexto_tipo,
        fecha_creacion=timezone.now(),
    )
    _copiar_contenido(version, nueva)
    return nueva


def errores_para_publicar(version):
    bloques, preguntas = cargar_estructura(version)
    errores = []
    if not preguntas:
        errores.append("El formulario no tiene preguntas.")
    for pregunta in preguntas:
        if pregunta.tipo in c.TIPOS_CON_OPCIONES and not pregunta.opciones.all():
            errores.append(f"La pregunta «{pregunta.texto[:60]}» no tiene opciones.")
    if sum(1 for p in preguntas if p.tipo == c.SELECTOR_PROGRAMA) > 1:
        errores.append("Un formulario solo puede tener un selector de programa.")
    return errores


def crear_enlace(version, usuario=None, **contexto):
    return EnlaceFormulario.objects.create(
        version=version,
        creado_por_usuario=usuario,
        token=uuid.uuid4(),
        fecha_inicio=timezone.now(),
        activo=True,
        **contexto,
    )


@transaction.atomic
def publicar(version, usuario=None, inicio=None, fin=None):
    """
    Publica la versión (CDE-100, CDE-104). Si otra versión del mismo formulario
    estaba publicada, se cierra y sus enlaces pasan a la nueva versión, así el
    enlace y el QR ya repartidos siguen funcionando.
    """
    if version.estado not in (c.BORRADOR, c.PUBLICADA):
        raise TransicionInvalida("Solo se puede publicar una versión en borrador.")
    errores = errores_para_publicar(version)
    if errores:
        raise TransicionInvalida(" ".join(errores))

    ahora = timezone.now()
    anteriores = version.plantilla.versiones.filter(estado=c.PUBLICADA).exclude(pk=version.pk)
    EnlaceFormulario.objects.filter(version__in=anteriores, activo=True).update(version=version)
    anteriores.update(estado=c.CERRADA, fecha_fin_vigencia=ahora)

    version.estado = c.PUBLICADA
    version.fecha_publicacion = version.fecha_publicacion or ahora
    version.fecha_inicio_vigencia = inicio
    version.fecha_fin_vigencia = fin
    version.save()

    enlace = version.enlaces.filter(activo=True).first()
    if enlace is None:
        enlace = crear_enlace(version, usuario)
    return enlace


def actualizar_vigencia(version, inicio=None, fin=None):
    version.fecha_inicio_vigencia = inicio
    version.fecha_fin_vigencia = fin
    version.save(update_fields=["fecha_inicio_vigencia", "fecha_fin_vigencia"])


def cerrar(version):
    """Deja de recibir respuestas (RF-FOR-04)."""
    if version.estado != c.PUBLICADA:
        raise TransicionInvalida("Solo se puede cerrar una versión publicada.")
    version.estado = c.CERRADA
    version.fecha_fin_vigencia = timezone.now()
    version.save(update_fields=["estado", "fecha_fin_vigencia"])


def reabrir(version):
    if version.estado != c.CERRADA:
        raise TransicionInvalida("Solo se puede reabrir una versión cerrada.")
    if version.plantilla.versiones.filter(estado=c.PUBLICADA).exclude(pk=version.pk).exists():
        raise TransicionInvalida("Ya hay otra versión publicada de este formulario.")
    version.estado = c.PUBLICADA
    version.fecha_fin_vigencia = None
    version.save(update_fields=["estado", "fecha_fin_vigencia"])


def archivar(version):
    if version.estado not in (c.BORRADOR, c.CERRADA):
        raise TransicionInvalida("Cierra la versión antes de archivarla.")
    version.estado = c.ARCHIVADA
    version.save(update_fields=["estado"])
    version.enlaces.update(activo=False)


def version_abierta(version, ahora=None):
    ahora = ahora or timezone.now()
    if version.estado != c.PUBLICADA:
        return False
    if version.fecha_inicio_vigencia and version.fecha_inicio_vigencia > ahora:
        return False
    if version.fecha_fin_vigencia and version.fecha_fin_vigencia < ahora:
        return False
    return True


def enlace_abierto(enlace, ahora=None):
    ahora = ahora or timezone.now()
    if not enlace.activo:
        return False
    if enlace.fecha_expiracion and enlace.fecha_expiracion < ahora:
        return False
    return version_abierta(enlace.version, ahora)


# ---------------------------------------------------------------------------
# Orden (CDE-100)
# ---------------------------------------------------------------------------

def siguiente_orden(queryset):
    return (queryset.aggregate(m=Max("orden"))["m"] or 0) + 1


def mover(objeto, hermanos, direccion):
    """Sube o baja un elemento dentro de sus hermanos, renumerando 1..n."""
    lista = list(hermanos.order_by("orden", "id"))
    indice = next(i for i, item in enumerate(lista) if item.pk == objeto.pk)
    destino = indice - 1 if direccion == "arriba" else indice + 1
    if 0 <= destino < len(lista):
        lista[indice], lista[destino] = lista[destino], lista[indice]
    _renumerar(lista)


def _renumerar(lista):
    for posicion, item in enumerate(lista, start=1):
        if item.orden != posicion:
            item.orden = posicion
            item.save(update_fields=["orden"])


def validar_orden_condiciones(version):
    """
    Una condición solo puede apuntar a una pregunta anterior (así la evalúa
    calcular_visibilidad). Si un cambio de orden la deja después, se avisa.
    """
    bloques, preguntas = cargar_estructura(version)
    textos = {p.id: p.texto for p in preguntas}
    anteriores = set()

    def revisar(regla, que):
        destino = (regla or {}).get("pregunta")
        if destino in textos and destino not in anteriores:
            raise TransicionInvalida(
                f"{que} depende de «{textos[destino][:60]}», que quedaría más abajo. "
                "Mueve primero esa pregunta o quita la condición."
            )

    por_bloque = {}
    for pregunta in preguntas:
        por_bloque.setdefault(pregunta.bloque_id, []).append(pregunta)
    for bloque in bloques:
        revisar(bloque.regla_visibilidad_json, f"La sección «{bloque.titulo[:60]}»")
        for pregunta in por_bloque.get(bloque.id, []):
            nombre = f"«{pregunta.texto[:60]}»"
            revisar(pregunta.regla_visibilidad_json, f"La pregunta {nombre}")
            for regla in (configuracion(pregunta).get("visibilidad_opciones") or {}).values():
                revisar(regla, f"Una opción de la pregunta {nombre}")
            anteriores.add(pregunta.id)


@transaction.atomic
def mover_pregunta(pregunta, direccion):
    asegurar_editable(pregunta.version)
    mover(pregunta, pregunta.version.preguntas.filter(bloque=pregunta.bloque), direccion)
    validar_orden_condiciones(pregunta.version)


@transaction.atomic
def mover_bloque(bloque, direccion):
    version = bloque.formulario_version
    asegurar_editable(version)
    mover(bloque, version.bloques.all(), direccion)
    validar_orden_condiciones(version)


@transaction.atomic
def ordenar_preguntas(version, bloque, ids):
    """Deja las preguntas `ids` en la sección `bloque` y en ese orden (arrastrar y soltar)."""
    asegurar_editable(version)
    preguntas = {p.id: p for p in version.preguntas.filter(pk__in=ids)}
    lista = []
    for pregunta_id in ids:
        pregunta = preguntas.get(pregunta_id)
        if pregunta is None:
            continue
        if pregunta.bloque_id != bloque.id:
            pregunta.bloque = bloque
            pregunta.save(update_fields=["bloque"])
        lista.append(pregunta)
    _renumerar(lista)
    validar_orden_condiciones(version)


def valor_desde_texto(texto, usados):
    base = slugify(texto).upper().replace("-", "_")[:100] or "OPCION"
    valor = base
    sufijo = 2
    while valor in usados:
        valor = f"{base[:110]}_{sufijo}"
        sufijo += 1
    usados.add(valor)
    return valor


@transaction.atomic
def guardar_opciones(pregunta, filas):
    """
    Reemplaza las opciones de la pregunta conservando el valor de las que ya
    existían. `filas` es una lista de dicts
    {id, texto, es_otras, programas, carrera_id}: `programas` limita la opción
    a ciertos programas del selector y `carrera_id` liga una opción del
    selector con su carrera (RF-FOR-05).

    Devuelve los ids de las opciones guardadas, en el orden de las filas con
    texto, para que el editor en vivo siga enviando los mismos ids.
    """
    existentes = {o.id: o for o in pregunta.opciones.all()}
    usados = set()
    conservadas = []
    reglas_opciones = {}
    datos_opciones = {}
    selector = next(
        (p for p in pregunta.version.preguntas.all() if p.tipo == c.SELECTOR_PROGRAMA),
        None,
    )

    for orden, fila in enumerate(filas, start=1):
        texto = fila["texto"].strip()
        if not texto:
            continue
        opcion = existentes.get(fila.get("id"))
        if opcion is not None:
            usados.add(opcion.valor)
            opcion.texto = texto
            opcion.orden = orden
            opcion.es_otras = bool(fila.get("es_otras"))
            opcion.save()
        else:
            opcion = OpcionPregunta.objects.create(
                pregunta=pregunta,
                texto=texto,
                valor=valor_desde_texto(texto, usados | {o.valor for o in existentes.values()}),
                orden=orden,
                es_otras=bool(fila.get("es_otras")),
            )
        conservadas.append(opcion.id)
        if fila.get("carrera_id"):
            datos_opciones[opcion.valor] = {"carrera_id": int(fila["carrera_id"])}
        programas = [v for v in fila.get("programas") or [] if v]
        if programas and selector and selector.id != pregunta.id:
            reglas_opciones[opcion.valor] = {"pregunta": selector.id, "valores": programas}

    for opcion_id, opcion in existentes.items():
        if opcion_id not in conservadas:
            opcion.delete()

    config = pregunta.configuracion_json or {}
    if reglas_opciones:
        config["visibilidad_opciones"] = reglas_opciones
    else:
        config.pop("visibilidad_opciones", None)
    if datos_opciones:
        config["opciones"] = datos_opciones
    else:
        config.pop("opciones", None)
    pregunta.configuracion_json = config or None
    pregunta.save(update_fields=["configuracion_json"])
    return conservadas


# ---------------------------------------------------------------------------
# Respuestas (CDE-106)
# ---------------------------------------------------------------------------

def _limpiar_rut(rut):
    return re.sub(r"[^0-9kK-]", "", rut or "").upper()


def _contexto_desde_enlace(enlace):
    contexto = {}
    if enlace is None:
        return contexto
    seccion = enlace.seccion or (enlace.equipo.seccion if enlace.equipo_id else None)
    if seccion is not None:
        contexto.update(
            seccion=seccion,
            campus=seccion.campus,
            sede=seccion.campus.sede,
            periodo=seccion.periodo,
            asignatura=seccion.asignatura,
            nrc_snapshot=seccion.nrc,
            seccion_snapshot=seccion.seccion,
        )
    if enlace.equipo_id:
        contexto["equipo"] = enlace.equipo
        if enlace.equipo.proyecto_id and not enlace.proyecto_id:
            contexto["proyecto"] = enlace.equipo.proyecto
    if enlace.proyecto_id:
        contexto["proyecto"] = enlace.proyecto
    if enlace.socio_id:
        contexto["socio"] = enlace.socio
    return contexto


def datos_respondente(preguntas, valores, visibles):
    """Nombre, correo y RUT de quien responde, según la configuración."""
    datos = {}
    for pregunta in preguntas:
        if pregunta.id not in visibles or not valores.get(pregunta.id):
            continue
        campo = configuracion(pregunta).get("dato_respondente")
        if not campo:
            if pregunta.tipo == c.RUT:
                campo = "rut"
            elif pregunta.tipo == c.CORREO:
                campo = "correo"
        if campo and campo not in datos:
            datos[campo] = str(valores[pregunta.id])
    return datos


def opcion_programa_elegida(preguntas, seleccion):
    selector = pregunta_selector(preguntas)
    if selector is None:
        return None, None
    elegido = next(iter(seleccion.get(selector.id, set())), None)
    opcion = next((o for o in selector.opciones.all() if o.valor == elegido), None)
    return selector, opcion


def existe_respuesta_duplicada(version, rut, valor_programa=None):
    """Un mismo RUT no responde dos veces el mismo formulario y programa."""
    if not rut:
        return False
    respuestas = RespuestaFormulario.objects.filter(
        version__plantilla=version.plantilla,
        respondente_rut=rut,
    )
    if valor_programa:
        respuestas = respuestas.filter(
            respuestas_preguntas__pregunta__tipo=c.SELECTOR_PROGRAMA,
            respuestas_preguntas__opciones_seleccionadas__opcion__valor=valor_programa,
        )
    return respuestas.exists()


@transaction.atomic
def guardar_respuesta(version, preguntas, valores, otros, visibles, seleccion,
                      enlace=None, usuario=None, archivos_guardar=None):
    """
    Guarda una respuesta completa en una sola transacción.

    `valores` es {pregunta_id: valor limpio} solo de preguntas visibles,
    `otros` es {pregunta_id: texto de la alternativa Otros}.
    """
    from archivos.services import guardar_archivo

    datos = datos_respondente(preguntas, valores, visibles)
    _, opcion_programa = opcion_programa_elegida(preguntas, seleccion)
    carrera_id = None
    if opcion_programa is not None:
        carrera_id = (configuracion_opcion(opcion_programa).get("carrera_id")) or None

    respuesta = RespuestaFormulario.objects.create(
        version=version,
        enlace=enlace,
        carrera_id=carrera_id,
        fecha_envio=timezone.now(),
        origen=c.ORIGEN_ENLACE,
        es_historica=False,
        respondente_tipo=version.contexto_tipo,
        respondente_nombre=datos.get("nombre"),
        respondente_correo=datos.get("correo"),
        respondente_rut=_limpiar_rut(datos.get("rut")) or None,
        estado_registro=c.ESTADO_REGISTRO_COMPLETO,
        **_contexto_desde_enlace(enlace),
    )

    for pregunta in preguntas:
        if pregunta.id not in visibles:
            continue
        valor = valores.get(pregunta.id)
        if valor in (None, "", [], ()):
            continue

        detalle = RespuestaPregunta(respuesta=respuesta, pregunta=pregunta)
        tipo = pregunta.tipo
        if tipo in (c.TEXTO_CORTO, c.TEXTO_LARGO):
            detalle.valor_texto = valor
        elif tipo == c.NUMERO:
            detalle.valor_numero = valor
        elif tipo == c.FECHA:
            detalle.valor_fecha = timezone.make_aware(datetime.combine(valor, time.min))
        elif tipo == c.CORREO:
            detalle.valor_correo = valor
        elif tipo == c.RUT:
            detalle.valor_rut = valor
        elif tipo == c.ESCALA:
            detalle.valor_escala = valor
        elif tipo in c.TIPOS_CON_OPCIONES:
            detalle.otro_texto = otros.get(pregunta.id) or None
        detalle.save()

        if tipo in c.TIPOS_CON_OPCIONES:
            elegidos = valor if isinstance(valor, (list, tuple)) else [valor]
            opciones = {o.valor: o for o in pregunta.opciones.all()}
            RespuestaOpcion.objects.bulk_create([
                RespuestaOpcion(respuesta_pregunta=detalle, opcion=opciones[v])
                for v in elegidos
                if v in opciones
            ])
        elif tipo == c.ARCHIVO:
            archivo = guardar_archivo(valor, autor=usuario if usuario and usuario.is_authenticated else None)
            RespuestaArchivo.objects.create(respuesta_pregunta=detalle, archivo=archivo)

    return respuesta


def configuracion_opcion(opcion):
    """Datos extra de una opción del selector (ej. la carrera asociada)."""
    config = configuracion(opcion.pregunta).get("opciones") or {}
    return config.get(opcion.valor) or {}


def _texto_detalle(detalle):
    """Texto legible de una respuesta a una pregunta."""
    pregunta = detalle.pregunta
    if pregunta.tipo in c.TIPOS_CON_OPCIONES:
        texto = ", ".join(sel.opcion.texto for sel in detalle.opciones_seleccionadas.all())
        if detalle.otro_texto:
            texto = f"{texto}: {detalle.otro_texto}" if texto else detalle.otro_texto
        return texto
    if pregunta.tipo == c.ARCHIVO:
        return ", ".join(a.archivo.nombre_original for a in detalle.archivos.all())
    if pregunta.tipo == c.ESCALA:
        maximo = configuracion(pregunta).get("maximo", c.ESCALA_MAXIMO_DEFECTO)
        return f"{detalle.valor_escala.normalize():f} de {maximo}"
    if pregunta.tipo == c.FECHA:
        return timezone.localtime(detalle.valor_fecha).strftime("%d/%m/%Y")
    if pregunta.tipo == c.NUMERO:
        return f"{detalle.valor_numero.normalize():f}"
    return detalle.valor_texto or detalle.valor_correo or detalle.valor_rut or ""


def _detalles(queryset):
    return queryset.select_related("pregunta").prefetch_related(
        "opciones_seleccionadas__opcion", "archivos__archivo",
    )


def resumen_respuesta(respuesta):
    """Lista (pregunta, texto de la respuesta) para mostrar al Coordinador."""
    detalles = _detalles(respuesta.respuestas_preguntas.all()).order_by(
        "pregunta__bloque__orden", "pregunta__orden", "pregunta__id",
    )
    return [(detalle.pregunta, _texto_detalle(detalle)) for detalle in detalles]


def respuestas_filtradas(version, valor_programa=None):
    """Respuestas de la versión, opcionalmente solo de un programa (pestaña)."""
    respuestas = version.respuestas.all()
    if valor_programa:
        respuestas = respuestas.filter(
            respuestas_preguntas__pregunta__tipo=c.SELECTOR_PROGRAMA,
            respuestas_preguntas__opciones_seleccionadas__opcion__valor=valor_programa,
        )
    return respuestas


def _conteo(opciones, cantidades, respondidas):
    return [
        {
            "texto": texto,
            "cantidad": cantidades[clave],
            "porcentaje": round(100 * cantidades[clave] / respondidas) if respondidas else 0,
        }
        for clave, texto in opciones
    ]


def estadisticas(version, valor_programa=None):
    """
    Resumen por pregunta, como la pestaña "Resumen" de Forms: cuántas veces se
    eligió cada opción, el promedio de una calificación y los textos escritos.
    """
    por_pregunta = {}
    detalles = _detalles(
        RespuestaPregunta.objects.filter(respuesta__in=respuestas_filtradas(version, valor_programa))
    ).order_by("-respuesta__fecha_envio")
    for detalle in detalles:
        por_pregunta.setdefault(detalle.pregunta_id, []).append(detalle)

    _, preguntas = cargar_estructura(version)
    resultado = []
    for pregunta in preguntas:
        lista = por_pregunta.get(pregunta.id, [])
        fila = {"pregunta": pregunta, "respondidas": len(lista)}
        if pregunta.tipo in c.TIPOS_CON_OPCIONES:
            cantidades = Counter(sel.opcion_id for d in lista for sel in d.opciones_seleccionadas.all())
            opciones = [(o.id, o.texto) for o in opciones_ordenadas(pregunta)]
            fila["opciones"] = _conteo(opciones, cantidades, len(lista))
            fila["textos"] = [d.otro_texto for d in lista if d.otro_texto]
        elif pregunta.tipo == c.ESCALA:
            config = configuracion(pregunta)
            minimo = config.get("minimo", c.ESCALA_MINIMO_DEFECTO)
            maximo = config.get("maximo", c.ESCALA_MAXIMO_DEFECTO)
            valores = [int(d.valor_escala) for d in lista if d.valor_escala is not None]
            fila["maximo"] = maximo
            fila["promedio"] = round(sum(valores) / len(valores), 1) if valores else None
            escala = [(n, str(n)) for n in range(maximo, minimo - 1, -1)]
            fila["opciones"] = _conteo(escala, Counter(valores), len(valores))
        else:
            fila["textos"] = [_texto_detalle(d) for d in lista]
        resultado.append(fila)
    return resultado


# ---------------------------------------------------------------------------
# Eliminar y duplicar en el constructor
# ---------------------------------------------------------------------------

def _quitar_reglas_que_apuntan_a(version, pregunta_id):
    """Al borrar una pregunta, las condiciones que dependían de ella se quitan."""
    for bloque in version.bloques.all():
        regla = bloque.regla_visibilidad_json
        if regla and regla.get("pregunta") == pregunta_id:
            bloque.regla_visibilidad_json = None
            bloque.save(update_fields=["regla_visibilidad_json"])
    for pregunta in version.preguntas.all():
        cambios = []
        regla = pregunta.regla_visibilidad_json
        if regla and regla.get("pregunta") == pregunta_id:
            pregunta.regla_visibilidad_json = None
            cambios.append("regla_visibilidad_json")
        config = pregunta.configuracion_json or {}
        reglas_opciones = config.get("visibilidad_opciones") or {}
        limpias = {k: v for k, v in reglas_opciones.items() if v and v.get("pregunta") != pregunta_id}
        if limpias != reglas_opciones:
            if limpias:
                config["visibilidad_opciones"] = limpias
            else:
                config.pop("visibilidad_opciones", None)
            pregunta.configuracion_json = config or None
            cambios.append("configuracion_json")
        if cambios:
            pregunta.save(update_fields=cambios)


@transaction.atomic
def eliminar_pregunta(pregunta):
    version = pregunta.version
    asegurar_editable(version)
    pregunta_id = pregunta.id
    pregunta.delete()
    _quitar_reglas_que_apuntan_a(version, pregunta_id)


@transaction.atomic
def eliminar_bloque(bloque):
    version = bloque.formulario_version
    asegurar_editable(version)
    if bloque.preguntas.exists():
        raise TransicionInvalida("La sección tiene preguntas. Muévelas o elimínalas primero.")
    if version.bloques.count() <= 1:
        raise TransicionInvalida("El formulario debe tener al menos una sección.")
    bloque.delete()


def _abrir_espacio(hermanos, orden):
    """Corre una posición hacia abajo los elementos desde `orden`."""
    for posterior in hermanos.filter(orden__gte=orden).order_by("-orden"):
        posterior.orden += 1
        posterior.save(update_fields=["orden"])


@transaction.atomic
def crear_pregunta_rapida(version, bloque, despues_de=None):
    """
    Agrega una pregunta lista para editar, como el "+" de Forms: queda bajo
    `despues_de` (o al final de la sección) con una primera opción.
    """
    asegurar_editable(version)
    hermanas = version.preguntas.filter(bloque=bloque)
    if despues_de is not None and despues_de.bloque_id == bloque.id:
        orden = despues_de.orden + 1
        _abrir_espacio(hermanas, orden)
    else:
        orden = siguiente_orden(hermanas)
    pregunta = PreguntaFormulario.objects.create(
        version=version,
        bloque=bloque,
        texto=c.PREGUNTA_NUEVA,
        tipo=c.ALTERNATIVA_UNICA,
        obligatoria=False,
        orden=orden,
    )
    OpcionPregunta.objects.create(
        pregunta=pregunta, texto=c.OPCION_NUEVA, valor=valor_desde_texto(c.OPCION_NUEVA, set()),
        orden=1, es_otras=False,
    )
    return pregunta


@transaction.atomic
def crear_seccion(version, despues_de=None):
    """Agrega una sección vacía bajo `despues_de` (o al final)."""
    asegurar_editable(version)
    if despues_de is not None:
        orden = despues_de.orden + 1
        _abrir_espacio(version.bloques.all(), orden)
    else:
        orden = siguiente_orden(version.bloques.all())
    return BloqueFormulario.objects.create(
        formulario_version=version,
        titulo=f"Sección {version.bloques.count() + 1}",
        orden=orden,
    )


@transaction.atomic
def duplicar_pregunta(pregunta):
    asegurar_editable(pregunta.version)
    if pregunta.tipo == c.SELECTOR_PROGRAMA:
        raise TransicionInvalida("El selector de programa no se puede duplicar.")
    _abrir_espacio(pregunta.version.preguntas.filter(bloque=pregunta.bloque), pregunta.orden + 1)
    copia = PreguntaFormulario.objects.create(
        version=pregunta.version,
        bloque=pregunta.bloque,
        texto=f"{pregunta.texto} (copia)",
        tipo=pregunta.tipo,
        obligatoria=pregunta.obligatoria,
        orden=pregunta.orden + 1,
        configuracion_json=copy.deepcopy(pregunta.configuracion_json),
        regla_visibilidad_json=copy.deepcopy(pregunta.regla_visibilidad_json),
    )
    OpcionPregunta.objects.bulk_create([
        OpcionPregunta(
            pregunta=copia, texto=o.texto, valor=o.valor, orden=o.orden, es_otras=o.es_otras,
        )
        for o in pregunta.opciones.all()
    ])
    return copia
