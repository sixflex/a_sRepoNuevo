from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import Archivo
from .permissions import puede_descargar_archivo
from .services import abrir_archivo


@login_required
def descargar_archivo(request, pk):
    archivo = get_object_or_404(Archivo, pk=pk)

    if not puede_descargar_archivo(request.user, archivo):
        raise PermissionDenied

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
