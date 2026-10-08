import json
import uuid

from django.contrib import messages
from django.db.models import Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from academico.models import Carrera
from core.qr import qr_base64
from usuarios.decorators import coordinador_required

from . import constantes as c
from . import services
from .forms import (
    FormularioDatosForm,
    PreguntaForm,
    RespuestaFormularioForm,
    SeccionForm,
    VigenciaForm,
)
from .models import (
    BloqueFormulario,
    EnlaceFormulario,
    FormularioPlantilla,
    FormularioVersion,
    PreguntaFormulario,
)

SESION_ENVIOS = "encuestas_envios"
ERRORES_CONSTRUCTOR = (services.FormularioNoEditable, services.TransicionInvalida)


def _version_o_404(version_id):
    return get_object_or_404(FormularioVersion.objects.select_related("plantilla"), pk=version_id)


def _redirigir_editor(version, ancla=None):
    url = reverse("encuestas:editor", args=[version.id])
    return redirect(f"{url}#{ancla}" if ancla else url)


def _es_fetch(request):
    """El constructor en vivo (encuestas_constructor.js) pide JSON con este encabezado."""
    return request.headers.get("X-Requested-With") == "fetch"


def _listo(request, version, ancla=None, mensaje=None, **datos):
    """Resultado de una acción del constructor: JSON para el editor en vivo o redirección."""
    if _es_fetch(request):
        return JsonResponse({"ok": True, **datos})
    if mensaje:
        messages.success(request, mensaje)
    return _redirigir_editor(version, ancla)


def _fallo(request, version, error, estado=400):
    if _es_fetch(request):
        return JsonResponse({"ok": False, "error": str(error)}, status=estado)
    messages.error(request, str(error))
    return _redirigir_editor(version)


def _bloquear_si_no_editable(request, version):
    """Devuelve una respuesta de error si la versión no se puede modificar (RN-17)."""
    if services.es_editable(version):
        return None
    return _fallo(
        request, version,
        "Esta versión ya tiene respuestas o está cerrada, así que no se modifica. "
        "Crea una nueva versión para hacer cambios.",
        estado=409,
    )


def _contexto_version(version, pestana):
    """Datos de la cabecera común (título, estado y pestañas Preguntas / Respuestas / Publicar)."""
    return {
        "version": version,
        "pestana": pestana,
        "estado_nombre": c.NOMBRES_ESTADO.get(version.estado, version.estado),
        "editable": services.es_editable(version),
        "tiene_respuestas": services.tiene_respuestas(version),
        "total_respuestas": version.respuestas.count(),
    }


# ---------------------------------------------------------------------------
# Lista y creación (CDE-100)
# ---------------------------------------------------------------------------

@coordinador_required
def lista_formularios(request):
    versiones = FormularioVersion.objects.annotate(total_respuestas=Count("respuestas")).order_by("-numero_version")
    plantillas = (
        FormularioPlantilla.objects
        .prefetch_related(Prefetch("versiones", queryset=versiones))
        .order_by("titulo")
    )
    filas = []
    for plantilla in plantillas:
        lista = list(plantilla.versiones.all())
        if not lista:
            continue
        vigente = next((v for v in lista if v.estado == c.PUBLICADA), lista[0])
        filas.append({
            "plantilla": plantilla,
            "vigente": vigente,
            "versiones": lista,
            "estado_nombre": c.NOMBRES_ESTADO.get(vigente.estado, vigente.estado),
        })
    return render(request, "encuestas/lista.html", {"filas": filas})


@coordinador_required
@require_POST
def crear_formulario(request):
    """Como "Nuevo formulario" en Forms: crea uno en blanco y abre el editor."""
    version = services.crear_formulario("Formulario sin título", request.user)
    return _redirigir_editor(version)


# ---------------------------------------------------------------------------
# Editor en una sola página (CDE-100 a CDE-103, CDE-105)
# ---------------------------------------------------------------------------

def _secciones_editor(version):
    """
    Secciones con sus tarjetas de pregunta. Cada tarjeta reutiliza el mismo
    render del formulario público (vista previa) más lo que el Coordinador
    necesita ver: tipo, condición y a qué programas aplica cada opción.
    """
    bloques, preguntas = services.cargar_estructura(version)
    textos = {p.id: p.texto for p in preguntas}
    opciones_texto = {p.id: {o.valor: o.texto for o in p.opciones.all()} for p in preguntas}

    def describir(regla):
        if not regla:
            return None
        pregunta_id = regla.get("pregunta")
        valores = [opciones_texto.get(pregunta_id, {}).get(v, v) for v in regla.get("valores", [])]
        return f"Solo si «{textos.get(pregunta_id, 'pregunta eliminada')[:60]}» es: {', '.join(valores)}"

    vista = RespuestaFormularioForm(version, bloques, preguntas).secciones()
    secciones = []
    for seccion in vista:
        tarjetas = []
        for item in seccion["preguntas"]:
            pregunta = item["pregunta"]
            reglas_opciones = item["config"].get("visibilidad_opciones") or {}
            item["visible"] = True
            restricciones = []
            for opcion in item["opciones"]:
                opcion["visible"] = True
                regla = reglas_opciones.get(opcion["opcion"].valor)
                if regla:
                    nombres = opciones_texto.get(regla.get("pregunta"), {})
                    restricciones.append({
                        "opcion": opcion["opcion"].texto,
                        "programas": ", ".join(nombres.get(v, v) for v in regla.get("valores", [])),
                    })
            item.update(
                tipo_nombre=c.NOMBRES_TIPO.get(pregunta.tipo, pregunta.tipo),
                icono=c.ICONOS_TIPO.get(pregunta.tipo, "bi-question-circle"),
                condicion=describir(pregunta.regla_visibilidad_json),
                restricciones=restricciones,
            )
            tarjetas.append(item)
        secciones.append({
            "bloque": seccion["bloque"],
            "condicion": describir(seccion["bloque"].regla_visibilidad_json),
            "tarjetas": tarjetas,
        })
    return secciones


def _html(request, plantilla, **contexto):
    return render_to_string(f"encuestas/includes/{plantilla}", contexto, request)


def _html_tarjeta(request, pregunta):
    version = pregunta.version
    for seccion in _secciones_editor(version):
        for item in seccion["tarjetas"]:
            if item["pregunta"].id == pregunta.id:
                return _html(request, "tarjeta_pregunta.html", item=item, editable=services.es_editable(version))
    return ""


def _html_seccion(request, bloque):
    version = bloque.formulario_version
    secciones = _secciones_editor(version)
    seccion = next(s for s in secciones if s["bloque"].id == bloque.id)
    return _html(
        request, "tarjeta_seccion.html",
        seccion=seccion, editable=services.es_editable(version), total_secciones=len(secciones),
    )


@coordinador_required
def editor(request, version_id):
    version = _version_o_404(version_id)
    secciones = _secciones_editor(version)
    datos_form = FormularioDatosForm(initial={
        "titulo": version.plantilla.titulo,
        "descripcion": version.plantilla.descripcion,
        "proceso": version.plantilla.proceso,
        "contexto_tipo": version.contexto_tipo,
    })
    return render(request, "encuestas/editor.html", {
        **_contexto_version(version, "preguntas"),
        "secciones": secciones,
        "total_secciones": len(secciones),
        "datos_form": datos_form,
    })


@coordinador_required
@require_POST
def editar_datos(request, version_id):
    version = _version_o_404(version_id)
    bloqueo = _bloquear_si_no_editable(request, version)
    if bloqueo:
        return bloqueo
    form = FormularioDatosForm(request.POST)
    if not form.is_valid():
        if _es_fetch(request):
            return JsonResponse({"ok": False, "errores": form.errors.get_json_data()}, status=400)
        messages.error(request, "Revisa los datos del formulario: el título y el proceso son obligatorios.")
        return _redirigir_editor(version)
    plantilla = version.plantilla
    plantilla.titulo = form.cleaned_data["titulo"]
    plantilla.descripcion = form.cleaned_data["descripcion"] or None
    plantilla.proceso = form.cleaned_data["proceso"]
    plantilla.save()
    version.contexto_tipo = form.cleaned_data["contexto_tipo"] or None
    version.save(update_fields=["contexto_tipo"])
    return _listo(request, version, mensaje="Datos del formulario guardados.")


@coordinador_required
@require_POST
def crear_seccion(request, version_id):
    version = _version_o_404(version_id)
    bloqueo = _bloquear_si_no_editable(request, version)
    if bloqueo:
        return bloqueo
    despues_de = version.bloques.filter(pk=request.POST.get("despues_de") or None).first()
    bloque = services.crear_seccion(version, despues_de)
    if _es_fetch(request):
        return JsonResponse({"ok": True, "id": bloque.id, "html": _html_seccion(request, bloque)})
    return redirect("encuestas:editar_seccion", bloque_id=bloque.id)


def _form_seccion(request, bloque):
    version = bloque.formulario_version
    primera = bloque.preguntas.order_by("orden", "id").first()
    condicionantes = [
        p for p in services.preguntas_condicionantes(version, antes_de=primera)
        if p.bloque is not None and p.bloque.orden < bloque.orden
    ]
    form = SeccionForm(request.POST or None, initial={"titulo": bloque.titulo, "descripcion": bloque.descripcion})
    form.configurar_regla(condicionantes, bloque.regla_visibilidad_json)
    return form, _opciones_condicion(condicionantes)


@coordinador_required
def editar_seccion(request, bloque_id):
    bloque = get_object_or_404(BloqueFormulario.objects.select_related("formulario_version__plantilla"), pk=bloque_id)
    version = bloque.formulario_version
    bloqueo = _bloquear_si_no_editable(request, version)
    if bloqueo:
        return bloqueo

    form, opciones_condicion = _form_seccion(request, bloque)
    contexto = {"version": version, "bloque": bloque, "form": form, "opciones_condicion": opciones_condicion}

    if request.method == "POST":
        if form.is_valid():
            bloque.titulo = form.cleaned_data["titulo"]
            bloque.descripcion = form.cleaned_data["descripcion"] or None
            bloque.regla_visibilidad_json = form.cleaned_data["regla"]
            bloque.save()
            if _es_fetch(request):
                return JsonResponse({"ok": True, "html": _html_seccion(request, bloque)})
            messages.success(request, "Sección guardada.")
            return _redirigir_editor(version, f"seccion-{bloque.id}")
        if _es_fetch(request):
            return JsonResponse({"ok": False, "errores": form.errors.get_json_data()}, status=400)
    elif _es_fetch(request):
        return JsonResponse({"ok": True, "html": _html(request, "editor_seccion.html", **contexto)})

    return render(request, "encuestas/seccion_form.html", contexto)


@coordinador_required
@require_POST
def eliminar_seccion(request, bloque_id):
    bloque = get_object_or_404(BloqueFormulario, pk=bloque_id)
    version = bloque.formulario_version
    try:
        services.eliminar_bloque(bloque)
    except ERRORES_CONSTRUCTOR as error:
        return _fallo(request, version, error)
    return _listo(request, version, mensaje="Sección eliminada.")


@coordinador_required
@require_POST
def mover_seccion(request, bloque_id, direccion):
    bloque = get_object_or_404(BloqueFormulario, pk=bloque_id)
    version = bloque.formulario_version
    try:
        services.mover_bloque(bloque, direccion)
    except ERRORES_CONSTRUCTOR as error:
        return _fallo(request, version, error)
    return _listo(request, version, f"seccion-{bloque.id}")


def _opciones_condicion(condicionantes):
    """{pregunta_id: [[valor, texto], ...]} para que el JS arme las casillas."""
    return json.dumps({
        p.id: [[o.valor, o.texto] for o in services.opciones_ordenadas(p)]
        for p in condicionantes
    })


def _filas_opciones(request):
    ids = request.POST.getlist("opcion_id")
    textos = request.POST.getlist("opcion_texto")
    otros = request.POST.getlist("opcion_otros")
    programas = request.POST.getlist("opcion_programas")
    carreras = request.POST.getlist("opcion_carrera")
    filas = []
    for i, texto in enumerate(textos):
        id_texto = ids[i] if i < len(ids) else ""
        filas.append({
            "id": int(id_texto) if id_texto.isdigit() else None,
            "texto": texto,
            "es_otras": (otros[i] if i < len(otros) else "0") == "1",
            "programas": [v for v in (programas[i] if i < len(programas) else "").split(",") if v],
            "carrera_id": carreras[i] if i < len(carreras) and carreras[i].isdigit() else None,
        })
    return filas


def _contexto_pregunta(version, pregunta, form, filas=None):
    selector = version.preguntas.filter(tipo=c.SELECTOR_PROGRAMA).prefetch_related("opciones").first()
    if pregunta is not None and selector is not None and selector.pk == pregunta.pk:
        programas = []
    else:
        programas = [(o.valor, o.texto) for o in services.opciones_ordenadas(selector)] if selector else []

    if filas is None:
        filas = []
        if pregunta is not None:
            config = services.configuracion(pregunta)
            reglas = config.get("visibilidad_opciones") or {}
            datos = config.get("opciones") or {}
            for opcion in services.opciones_ordenadas(pregunta):
                filas.append({
                    "id": opcion.id,
                    "texto": opcion.texto,
                    "es_otras": opcion.es_otras,
                    "programas": (reglas.get(opcion.valor) or {}).get("valores", []),
                    "carrera_id": (datos.get(opcion.valor) or {}).get("carrera_id"),
                })

    condicionantes = services.preguntas_condicionantes(version, antes_de=pregunta)
    return {
        "version": version,
        "pregunta": pregunta,
        "form": form,
        "filas_opciones": filas,
        "programas": programas,
        "carreras": Carrera.objects.filter(activo=True).order_by("nombre"),
        "tipos_con_opciones": json.dumps(sorted(c.TIPOS_CON_OPCIONES)),
        "iconos_tipo": json.dumps(c.ICONOS_TIPO),
        "opciones_condicion": _opciones_condicion(condicionantes),
    }


def _guardar_pregunta(request, version, pregunta=None):
    form = PreguntaForm(request.POST or None, version=version, pregunta=pregunta)
    if request.method != "POST":
        if pregunta is None and request.GET.get("bloque"):
            form.initial["bloque"] = request.GET["bloque"]
        contexto = _contexto_pregunta(version, pregunta, form)
        if _es_fetch(request):
            return JsonResponse({"ok": True, "html": _html(request, "editor_pregunta.html", **contexto)})
        return render(request, "encuestas/pregunta_form.html", {**contexto, "pagina_completa": True})

    filas = _filas_opciones(request)
    tipo = request.POST.get("tipo")
    if form.is_valid() and tipo in c.TIPOS_CON_OPCIONES and not any(f["texto"].strip() for f in filas):
        form.add_error(None, "Agrega al menos una opción.")
    if not form.is_valid():
        if _es_fetch(request):
            return JsonResponse({"ok": False, "errores": form.errors.get_json_data()}, status=400)
        contexto = _contexto_pregunta(version, pregunta, form, filas)
        return render(request, "encuestas/pregunta_form.html", {**contexto, "pagina_completa": True})

    datos = form.cleaned_data
    nueva = pregunta is None
    if nueva:
        pregunta = PreguntaFormulario(version=version)
    if nueva or pregunta.bloque_id != datos["bloque"].id:
        pregunta.orden = services.siguiente_orden(version.preguntas.filter(bloque=datos["bloque"]))
    pregunta.bloque = datos["bloque"]
    pregunta.texto = datos["texto"].strip()
    pregunta.tipo = datos["tipo"]
    pregunta.obligatoria = datos["obligatoria"]
    pregunta.regla_visibilidad_json = datos["regla"]
    pregunta.configuracion_json = form.configuracion(pregunta.configuracion_json if not nueva else None)
    pregunta.save()

    ids_opciones = []
    if pregunta.tipo in c.TIPOS_CON_OPCIONES:
        for fila in filas:
            # La carrera solo aplica a las pestañas; "Solo para" solo al resto.
            if pregunta.tipo == c.SELECTOR_PROGRAMA:
                fila["programas"] = []
            else:
                fila["carrera_id"] = None
        ids_opciones = services.guardar_opciones(pregunta, filas)
    else:
        pregunta.opciones.all().delete()

    if _es_fetch(request):
        return JsonResponse({
            "ok": True, "id": pregunta.id, "opciones": ids_opciones, "html": _html_tarjeta(request, pregunta),
        })
    messages.success(request, "Pregunta guardada.")
    if "guardar_y_otra" in request.POST:
        return redirect(f"{reverse('encuestas:crear_pregunta', args=[version.id])}?bloque={pregunta.bloque_id}")
    return _redirigir_editor(version, f"pregunta-{pregunta.id}")


@coordinador_required
def crear_pregunta(request, version_id):
    version = _version_o_404(version_id)
    bloqueo = _bloquear_si_no_editable(request, version)
    if bloqueo:
        return bloqueo
    if request.method == "POST" and _es_fetch(request):
        # Botón "+ Pregunta" del editor en vivo: la crea y la abre para editar.
        bloque = get_object_or_404(version.bloques, pk=request.POST.get("bloque"))
        despues_de = version.preguntas.filter(pk=request.POST.get("despues_de") or None).first()
        pregunta = services.crear_pregunta_rapida(version, bloque, despues_de)
        return JsonResponse({"ok": True, "id": pregunta.id, "html": _html_tarjeta(request, pregunta)})
    return _guardar_pregunta(request, version)


@coordinador_required
def editar_pregunta(request, pregunta_id):
    pregunta = get_object_or_404(PreguntaFormulario.objects.select_related("version__plantilla"), pk=pregunta_id)
    bloqueo = _bloquear_si_no_editable(request, pregunta.version)
    if bloqueo:
        return bloqueo
    return _guardar_pregunta(request, pregunta.version, pregunta)


@coordinador_required
@require_POST
def eliminar_pregunta(request, pregunta_id):
    pregunta = get_object_or_404(PreguntaFormulario, pk=pregunta_id)
    version = pregunta.version
    try:
        services.eliminar_pregunta(pregunta)
    except ERRORES_CONSTRUCTOR as error:
        return _fallo(request, version, error)
    return _listo(request, version, mensaje="Pregunta eliminada.")


@coordinador_required
@require_POST
def duplicar_pregunta(request, pregunta_id):
    pregunta = get_object_or_404(PreguntaFormulario, pk=pregunta_id)
    try:
        copia = services.duplicar_pregunta(pregunta)
    except ERRORES_CONSTRUCTOR as error:
        return _fallo(request, pregunta.version, error)
    if _es_fetch(request):
        return JsonResponse({"ok": True, "id": copia.id, "html": _html_tarjeta(request, copia)})
    messages.success(request, "Pregunta duplicada.")
    return _redirigir_editor(pregunta.version, f"pregunta-{copia.id}")


@coordinador_required
@require_POST
def mover_pregunta(request, pregunta_id, direccion):
    pregunta = get_object_or_404(PreguntaFormulario, pk=pregunta_id)
    try:
        services.mover_pregunta(pregunta, direccion)
    except ERRORES_CONSTRUCTOR as error:
        return _fallo(request, pregunta.version, error)
    return _listo(request, pregunta.version, f"pregunta-{pregunta.id}")


@coordinador_required
@require_POST
def ordenar_preguntas(request, version_id):
    """Arrastrar y soltar: recibe la sección de destino y el orden de sus preguntas."""
    version = _version_o_404(version_id)
    bloque = get_object_or_404(version.bloques, pk=request.POST.get("bloque"))
    ids = [int(i) for i in request.POST.getlist("preguntas") if i.isdigit()]
    try:
        services.ordenar_preguntas(version, bloque, ids)
    except ERRORES_CONSTRUCTOR as error:
        return _fallo(request, version, error)
    return _listo(request, version)


# ---------------------------------------------------------------------------
# Versiones, publicación, enlace y QR (CDE-100, CDE-104, CDE-105)
# ---------------------------------------------------------------------------

@coordinador_required
@require_POST
def nueva_version(request, version_id):
    version = _version_o_404(version_id)
    nueva = services.crear_nueva_version(version, request.user)
    messages.success(request, f"Se creó la versión {nueva.numero_version} en borrador. Las respuestas anteriores siguen en la versión {version.numero_version}.")
    return _redirigir_editor(nueva)


@coordinador_required
@require_POST
def copiar_formulario(request, version_id):
    version = _version_o_404(version_id)
    copia = services.copiar_formulario(version, request.user)
    messages.success(request, "Formulario copiado como borrador nuevo.")
    return _redirigir_editor(copia)


@coordinador_required
def publicacion(request, version_id):
    version = _version_o_404(version_id)
    vigencia = VigenciaForm(
        request.POST if request.POST.get("accion") in ("publicar", "vigencia") else None,
        initial={
            "fecha_inicio_vigencia": version.fecha_inicio_vigencia,
            "fecha_fin_vigencia": version.fecha_fin_vigencia,
        },
    )

    if request.method == "POST":
        accion = request.POST.get("accion")
        try:
            if accion == "publicar":
                if vigencia.is_valid():
                    services.publicar(
                        version, request.user,
                        vigencia.cleaned_data["fecha_inicio_vigencia"],
                        vigencia.cleaned_data["fecha_fin_vigencia"],
                    )
                    messages.success(request, "Formulario publicado. Ya puedes compartir el enlace o el QR.")
                    return redirect("encuestas:publicacion", version_id=version.id)
            elif accion == "vigencia":
                if vigencia.is_valid():
                    services.actualizar_vigencia(
                        version,
                        vigencia.cleaned_data["fecha_inicio_vigencia"],
                        vigencia.cleaned_data["fecha_fin_vigencia"],
                    )
                    messages.success(request, "Vigencia actualizada.")
                    return redirect("encuestas:publicacion", version_id=version.id)
            elif accion == "cerrar":
                services.cerrar(version)
                messages.success(request, "Formulario cerrado: ya no recibe respuestas.")
                return redirect("encuestas:publicacion", version_id=version.id)
            elif accion == "reabrir":
                services.reabrir(version)
                messages.success(request, "Formulario reabierto.")
                return redirect("encuestas:publicacion", version_id=version.id)
            elif accion == "archivar":
                services.archivar(version)
                messages.success(request, "Versión archivada.")
                return redirect("encuestas:lista")
        except services.TransicionInvalida as error:
            messages.error(request, str(error))
            return redirect("encuestas:publicacion", version_id=version.id)

    enlace = version.enlaces.filter(activo=True).order_by("id").first()
    url_publica = qr = None
    if enlace is not None:
        url_publica = request.build_absolute_uri(reverse("encuestas:responder", args=[enlace.token]))
        qr = qr_base64(url_publica)

    return render(request, "encuestas/publicacion.html", {
        **_contexto_version(version, "publicar"),
        "vigencia": vigencia,
        "enlace": enlace,
        "url_publica": url_publica,
        "qr_base64": qr,
        "abierta": services.version_abierta(version),
        "errores_publicar": services.errores_para_publicar(version) if version.estado == c.BORRADOR else [],
    })


@coordinador_required
def vista_previa(request, version_id):
    version = _version_o_404(version_id)
    bloques, preguntas = services.cargar_estructura(version)
    form = RespuestaFormularioForm(version, bloques, preguntas)
    return render(request, "encuestas/responder.html", {
        "version": version,
        "form": form,
        "vista_previa": True,
        "hide_sidebar": True,
    })


@coordinador_required
def respuestas(request, version_id):
    """Pestaña Respuestas: "Resumen" por pregunta e "Individual" por persona, como en Forms."""
    version = _version_o_404(version_id)
    _, preguntas = services.cargar_estructura(version)
    selector = services.pregunta_selector(preguntas)
    programas = [(o.valor, o.texto) for o in services.opciones_ordenadas(selector)] if selector else []
    programa = request.GET.get("programa") or ""
    if programa not in {valor for valor, _ in programas}:
        programa = ""

    lista = (
        services.respuestas_filtradas(version, programa)
        .select_related("carrera", "seccion")
        .order_by("-fecha_envio")
    )
    filas = [{"respuesta": r, "detalle": services.resumen_respuesta(r)} for r in lista]
    return render(request, "encuestas/respuestas.html", {
        **_contexto_version(version, "respuestas"),
        "filas": filas,
        "resumen": services.estadisticas(version, programa),
        "programas": programas,
        "programa": programa,
    })


# ---------------------------------------------------------------------------
# Público: responder por enlace (CDE-103, CDE-104, CDE-106)
# ---------------------------------------------------------------------------

def _envios_de_sesion(request):
    return request.session.get(SESION_ENVIOS, {})


def responder(request, token):
    enlace = get_object_or_404(
        EnlaceFormulario.objects.select_related("version__plantilla"), token=token,
    )
    version = enlace.version
    contexto = {"version": version, "enlace": enlace, "hide_sidebar": True}

    if not services.enlace_abierto(enlace):
        return render(request, "encuestas/cerrado.html", contexto)

    bloques, preguntas = services.cargar_estructura(version)
    form = RespuestaFormularioForm(version, bloques, preguntas, request.POST or None, request.FILES or None)

    if request.method == "POST":
        clave = request.POST.get("clave_envio", "")
        envios = _envios_de_sesion(request)
        if clave and clave in envios:
            # Recarga o doble clic: no se crea una segunda respuesta (RNF-DAT-02).
            return redirect("encuestas:enviado", token=enlace.token)

        if form.is_valid():
            rut = services.datos_respondente(preguntas, form.valores, form.visibilidad[1]).get("rut")
            _, opcion_programa = services.opcion_programa_elegida(preguntas, form.seleccion)
            valor_programa = opcion_programa.valor if opcion_programa else None
            if services.existe_respuesta_duplicada(version, rut, valor_programa):
                form.add_error(None, "Ya existe una respuesta registrada con este RUT para este formulario.")
            else:
                respuesta = services.guardar_respuesta(
                    version, preguntas, form.valores, form.otros, form.visibilidad[1], form.seleccion,
                    enlace=enlace, usuario=request.user,
                )
                envios[clave or str(respuesta.id)] = respuesta.id
                request.session[SESION_ENVIOS] = envios
                request.session["encuestas_ultimo_folio"] = respuesta.id
                return redirect("encuestas:enviado", token=enlace.token)

    contexto.update(form=form, clave_envio=request.POST.get("clave_envio") or uuid.uuid4().hex)
    return render(request, "encuestas/responder.html", contexto)


def enviado(request, token):
    enlace = get_object_or_404(EnlaceFormulario.objects.select_related("version__plantilla"), token=token)
    return render(request, "encuestas/enviado.html", {
        "version": enlace.version,
        "folio": request.session.get("encuestas_ultimo_folio"),
        "hide_sidebar": True,
    })
