from django.core.files.storage import FileSystemStorage


class PrivateFileSystemStorage(FileSystemStorage):
    """Storage local sin URL pública para archivos privados."""

    def url(self, name):
        raise NotImplementedError(
            "Los archivos privados no exponen una URL directa. "
            "Use el endpoint autorizado de descarga."
        )
