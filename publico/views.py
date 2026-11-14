from django.contrib import messages
from django.shortcuts import redirect, render

from usuarios.decorators import coordinador_required

from . import portal


@coordinador_required
def configurar_portal(request):
    """Pestaña "Qué se muestra" de Portal público (RF-PUB-01)."""
    configuracion = portal.obtener_configuracion()
    errores = []

    if request.method == "POST":
        opciones, errores = portal.leer_formulario(request.POST)
        if not errores:
            portal.guardar_configuracion(opciones, request)
            messages.success(request, "Listo: el portal público ya muestra lo que elegiste.")
            return redirect("publico:configurar_portal")
        # Se vuelve a mostrar lo que marcó, sin perderlo (RNF-USA-02).
        configuracion.opciones_json = opciones

    return render(request, "publico/configurar_portal.html", {
        "bloques": portal.bloques_para_formulario(configuracion),
        "configuracion": configuracion,
        "errores": errores,
    })


# ---------------------------------------------------------------------------
# Noticias (RF-PUB-03, RF-PUB-04)
# ---------------------------------------------------------------------------

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from auditoria.services import registrar_auditoria

from . import noticias as servicio_noticias
from .forms import NoticiaForm
from .models import Noticia


@coordinador_required
def noticias(request):
    """
    Pestaña "Noticias" de Portal público. Se pega el enlace, el sistema lee
    la noticia y el Coordinador revisa y publica. Si no se puede leer, la
    completa a mano.
    """
    form = None
    aviso_lectura = ""
    leida = False

    if request.method == "POST" and request.POST.get("accion") == "leer":
        url = servicio_noticias.normalizar_url(request.POST.get("url", ""))
        if not url:
            aviso_lectura = "Pega el enlace de la noticia."
        elif Noticia.objects.filter(url_fuente__in=[url, url + "/"]).exists():
            aviso_lectura = "Esta noticia ya está agregada."
        else:
            try:
                datos = servicio_noticias.leer_noticia(url)
                leida = True
            except servicio_noticias.NoticiaNoLeida as error:
                aviso_lectura = str(error)
                datos = {"url_fuente": url, "fecha_publicacion": timezone.now(), "fuente": ""}
            datos["fecha_publicacion"] = timezone.localtime(datos["fecha_publicacion"]).date()
            form = NoticiaForm(initial=datos)

    elif request.method == "POST":
        form = NoticiaForm(request.POST)
        leida = request.POST.get("leida") == "1"
        if form.is_valid():
            noticia = form.save(commit=False)
            noticia.estado = servicio_noticias.PUBLICADA
            noticia.fecha_sincronizacion = timezone.now() if leida else None
            noticia.save()
            registrar_auditoria(
                request=request, entidad="Noticia", entidad_id=noticia.pk, accion="CREAR",
                valores_nuevos={"titulo": noticia.titulo, "url_fuente": noticia.url_fuente},
            )
            messages.success(request, f"Publicada: «{noticia.titulo}».")
            return redirect("publico:noticias")

    return render(request, "publico/noticias.html", {
        "form": form,
        "leida": leida,
        "aviso_lectura": aviso_lectura,
        "noticias": Noticia.objects.order_by("-fecha_publicacion", "-id"),
        "busqueda_ua": servicio_noticias.BUSQUEDA_UA,
        "noticias_activas": portal.configuracion_portal()["noticias"]["activo"],
    })


@coordinador_required
@require_POST
def cambiar_estado_noticia(request, noticia_id):
    """Oculta una noticia que no corresponde o la vuelve a mostrar (RF-PUB-03 CA1)."""
    noticia = get_object_or_404(Noticia, pk=noticia_id)
    anterior = noticia.estado
    noticia.estado = (
        servicio_noticias.OCULTA if anterior == servicio_noticias.PUBLICADA else servicio_noticias.PUBLICADA
    )
    noticia.save(update_fields=["estado"])
    registrar_auditoria(
        request=request, entidad="Noticia", entidad_id=noticia.pk, accion="CAMBIAR_ESTADO",
        valores_anteriores={"estado": anterior}, valores_nuevos={"estado": noticia.estado},
    )
    if noticia.estado == servicio_noticias.OCULTA:
        messages.success(request, f"Oculta del portal: «{noticia.titulo}».")
    else:
        messages.success(request, f"Visible otra vez en el portal: «{noticia.titulo}».")
    return redirect("publico:noticias")


@coordinador_required
@require_POST
def eliminar_noticia(request, noticia_id):
    noticia = get_object_or_404(Noticia, pk=noticia_id)
    registrar_auditoria(
        request=request, entidad="Noticia", entidad_id=noticia.pk, accion="ELIMINAR",
        valores_anteriores={"titulo": noticia.titulo, "url_fuente": noticia.url_fuente},
    )
    titulo = noticia.titulo
    noticia.delete()
    messages.success(request, f"Eliminada: «{titulo}».")
    return redirect("publico:noticias")
