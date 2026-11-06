from itertools import groupby

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from auditoria.services import registrar_auditoria
from usuarios.decorators import coordinador_required

from .forms import CATEGORIAS, RecursoRepositorioForm
from .models import Archivo, RecursoRepositorio
from .permissions import puede_descargar_archivo
from .services import abrir_archivo, guardar_archivo


PUBLICADO = "PUBLICADO"
RETIRADO = "RETIRADO"


@login_required
def descargar_archivo(request, pk):
    archivo = get_object_or_404(Archivo, pk=pk)

    if not puede_descargar_archivo(request.user, archivo):
        raise PermissionDenied

    return _respuesta_archivo(archivo)


def _respuesta_archivo(archivo):
    try:
        contenido = abrir_archivo(archivo)
    except FileNotFoundError as exc:
        raise Http404("El archivo físico no está disponible.") from exc

    return FileResponse(
        contenido,
        as_attachment=True,
        filename=archivo.nombre_original,
        content_type=archivo.mime_type,
    )


# ---------------------------------------------------------------------------
# Repositorio de recursos (RF-PUB-02)
# ---------------------------------------------------------------------------

def _datos_auditoria(recurso):
    return {
        "titulo": recurso.titulo,
        "categoria": recurso.categoria,
        "visibilidad": recurso.visibilidad,
        "estado": recurso.estado,
        "archivo": recurso.archivo.nombre_original if recurso.archivo_id else None,
        "url_externa": recurso.url_externa,
    }


def _por_categoria(recursos):
    """[(categoría, [recursos])] en el orden de CATEGORIAS; las desconocidas al final."""
    orden = {valor: i for i, (valor, _) in enumerate(CATEGORIAS)}
    recursos = sorted(
        recursos,
        key=lambda r: (orden.get(r.categoria, len(orden)), r.categoria, r.titulo.lower()),
    )
    return [(categoria, list(grupo)) for categoria, grupo in groupby(recursos, key=lambda r: r.categoria)]


@coordinador_required
def repositorio(request):
    recursos = RecursoRepositorio.objects.select_related("archivo", "publicado_por_usuario")
    return render(request, "archivos/repositorio.html", {
        "grupos": _por_categoria(recursos),
        "total": recursos.count(),
        "publicos": recursos.filter(visibilidad="PUBLICO", estado=PUBLICADO).count(),
    })


@coordinador_required
def crear_recurso(request):
    return _guardar_recurso(request, RecursoRepositorio())


@coordinador_required
def editar_recurso(request, pk):
    return _guardar_recurso(request, get_object_or_404(RecursoRepositorio, pk=pk))


def _guardar_recurso(request, recurso):
    nuevo = recurso.pk is None
    anteriores = None if nuevo else _datos_auditoria(recurso)
    form = RecursoRepositorioForm(request.POST or None, request.FILES or None, instance=recurso)

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                recurso = form.save(commit=False)
                subido = form.cleaned_data.get("archivo_subido")
                if subido:
                    # Reemplazar no borra el archivo anterior: queda en el almacenamiento.
                    recurso.archivo = guardar_archivo(subido, autor=request.user)
                if nuevo:
                    recurso.estado = PUBLICADO
                    recurso.publicado_por_usuario = request.user
                    recurso.fecha_publicacion = timezone.now()
                recurso.save()
                registrar_auditoria(
                    request=request,
                    entidad="RecursoRepositorio",
                    entidad_id=recurso.pk,
                    accion="CREAR_RECURSO" if nuevo else "EDITAR_RECURSO",
                    valores_anteriores=anteriores,
                    valores_nuevos=_datos_auditoria(recurso),
                )
        except ValidationError as error:
            form.add_error("archivo_subido", error)
        else:
            messages.success(request, f"«{recurso.titulo}» quedó guardado.")
            return redirect("archivos:repositorio")

    return render(request, "archivos/recurso_form.html", {"form": form, "recurso": recurso, "nuevo": nuevo})


@coordinador_required
@require_POST
def cambiar_estado_recurso(request, pk):
    recurso = get_object_or_404(RecursoRepositorio, pk=pk)
    anteriores = _datos_auditoria(recurso)
    retirar = recurso.estado == PUBLICADO
    recurso.estado = RETIRADO if retirar else PUBLICADO
    if not retirar:
        recurso.fecha_publicacion = timezone.now()
    recurso.save(update_fields=["estado", "fecha_publicacion"])
    registrar_auditoria(
        request=request,
        entidad="RecursoRepositorio",
        entidad_id=recurso.pk,
        accion="RETIRAR_RECURSO" if retirar else "PUBLICAR_RECURSO",
        valores_anteriores=anteriores,
        valores_nuevos=_datos_auditoria(recurso),
    )
    messages.success(
        request,
        f"«{recurso.titulo}» se retiró del portal." if retirar else f"«{recurso.titulo}» volvió a publicarse.",
    )
    return redirect("archivos:repositorio")


@coordinador_required
@require_POST
def eliminar_recurso(request, pk):
    # Elimina la ficha del repositorio; el archivo queda en el almacenamiento.
    recurso = get_object_or_404(RecursoRepositorio.objects.select_related("archivo"), pk=pk)
    anteriores = _datos_auditoria(recurso)
    recurso.delete()
    registrar_auditoria(
        request=request,
        entidad="RecursoRepositorio",
        entidad_id=pk,
        accion="ELIMINAR_RECURSO",
        valores_anteriores=anteriores,
    )
    messages.success(request, f"«{anteriores['titulo']}» se eliminó del repositorio.")
    return redirect("archivos:repositorio")


@coordinador_required
def descargar_recurso(request, pk):
    recurso = get_object_or_404(RecursoRepositorio.objects.select_related("archivo"), pk=pk)
    if not recurso.archivo_id:
        raise Http404
    return _respuesta_archivo(recurso.archivo)


# Portal público, sin sesión: solo recursos públicos y publicados.

def recursos_publicos():
    return RecursoRepositorio.objects.filter(
        visibilidad="PUBLICO", estado=PUBLICADO,
    ).select_related("archivo")


def repositorio_publico(request):
    return render(request, "archivos/repositorio_publico.html", {
        "grupos": _por_categoria(recursos_publicos()),
        "hide_sidebar": True,
    })


def descargar_recurso_publico(request, pk):
    recurso = get_object_or_404(recursos_publicos(), pk=pk)
    if not recurso.archivo_id:
        raise Http404
    return _respuesta_archivo(recurso.archivo)

# Gestión de Noticias Manuales (CDE-611 / CDE-612)
from core.models import Noticia
from .forms import NoticiaForm

@coordinador_required
def crear_noticia(request):
    """
    Permite a la coordinación publicar noticias manualmente por enlace (CDE-612).
    Aplica la validación de NoticiaForm para no duplicar por URL.
    """
    form = NoticiaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        noticia = form.save()
        messages.success(request, f"La noticia «{noticia.titulo}» ha sido publicada.")
        return redirect("core:inicio")

    return render(request, "archivos/noticia_form.html", {"form": form})