from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

EXTENSIONES_PERMITIDAS = {"pdf","doc","docx","xls","xlsx","jpg","jpeg","png",}

def validar_tamano_archivo(archivo):
    limite_mb = settings.PRIVATE_STORAGE_MAX_FILE_SIZE_MB
    limite_bytes = limite_mb * 1024 * 1024

    if archivo.size > limite_bytes:
        raise ValidationError(
            f"El archivo supera el límite configurado de {limite_mb} MB.",
            code="archivo_demasiado_grande",
        )

def validar_extension_archivo(archivo):
    extension = Path(
        archivo.name or ""
    ).suffix.lower().lstrip(".")

    if extension not in EXTENSIONES_PERMITIDAS:
        raise ValidationError(
            "Formato no permitido. Solo se aceptan PDF, DOC, DOCX, XLS, XLSX, JPG y PNG.",
            code="extension_no_permitida",
        )

def validar_cantidad_archivos(cantidad_actual, cantidad_nueva=1, limite=None):
    limite = (
        settings.PRIVATE_STORAGE_MAX_FILES_PER_ACTIVITY
        if limite is None
        else limite
    )

    if cantidad_actual + cantidad_nueva > limite:
        raise ValidationError(
            f"Se supera el límite configurado de {limite} archivos.",
            code="demasiados_archivos",
        )