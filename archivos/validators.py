from django.conf import settings
from django.core.exceptions import ValidationError


def validar_tamano_archivo(archivo):
    limite_mb = settings.PRIVATE_STORAGE_MAX_FILE_SIZE_MB
    limite_bytes = limite_mb * 1024 * 1024

    if archivo.size > limite_bytes:
        raise ValidationError(
            f"El archivo supera el límite configurado de {limite_mb} MB.",
            code="archivo_demasiado_grande",
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
