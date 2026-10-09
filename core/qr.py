"""Código QR en base64 para mostrar en plantillas (misma técnica que registro de equipos)."""

import base64
from io import BytesIO

import qrcode


def qr_base64(texto):
    imagen = qrcode.make(texto)
    buffer = BytesIO()
    imagen.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
