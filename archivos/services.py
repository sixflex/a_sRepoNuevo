import hashlib
import mimetypes
import uuid
from pathlib import Path

from django.core.files.storage import storages
from django.utils import timezone

from .models import Archivo
from .validators import validar_tamano_archivo


def obtener_storage_privado():
    return storages["private"]


def _nombre_seguro(nombre):
    return Path(nombre or "archivo").name


def _extension(nombre):
    return Path(nombre).suffix.lower().lstrip(".")


def _mime_type(archivo, nombre):
    return (
        getattr(archivo, "content_type", None)
        or mimetypes.guess_type(nombre)[0]
        or "application/octet-stream"
    )


def _hash_sha256(archivo):
    digest = hashlib.sha256()

    if hasattr(archivo, "chunks"):
        for chunk in archivo.chunks():
            digest.update(chunk)
    else:
        for chunk in iter(lambda: archivo.read(1024 * 1024), b""):
            digest.update(chunk)

    if hasattr(archivo, "seek"):
        archivo.seek(0)

    return digest.hexdigest()


def _generar_storage_key(nombre):
    ahora = timezone.now()
    sufijo = Path(nombre).suffix.lower()

    return (
        f"{ahora:%Y/%m}/"
        f"{uuid.uuid4().hex}{sufijo}"
    )


def guardar_archivo(archivo_subido, autor=None, storage=None):
    """Guarda el binario fuera de PostgreSQL y persiste solo metadatos."""
    validar_tamano_archivo(archivo_subido)

    storage = storage or obtener_storage_privado()
    nombre = _nombre_seguro(archivo_subido.name)
    storage_key = _generar_storage_key(nombre)
    hash_sha256 = _hash_sha256(archivo_subido)

    storage_key_guardado = storage.save(storage_key, archivo_subido)

    try:
        return Archivo.objects.create(
            cargado_por_usuario=autor,
            nombre_original=nombre,
            extension=_extension(nombre),
            storage_key=storage_key_guardado,
            mime_type=_mime_type(archivo_subido, nombre),
            tamano_bytes=archivo_subido.size,
            hash_sha256=hash_sha256,
        )
    except Exception:
        storage.delete(storage_key_guardado)
        raise


def abrir_archivo(archivo, storage=None):
    """Abre un Archivo mediante el proveedor configurado, sin exponer rutas."""
    storage = storage or obtener_storage_privado()
    return storage.open(archivo.storage_key, mode="rb")
