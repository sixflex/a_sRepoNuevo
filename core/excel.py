from io import BytesIO

from django.http import HttpResponse
from openpyxl import Workbook


CONTENT_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def celda_texto(cell, valor):
    """Escribe un valor como texto, conservando ceros iniciales."""
    cell.value = "" if valor is None else str(valor)
    cell.data_type = "s"
    cell.number_format = "@"
    return cell


def agregar_metadatos(hoja, metadatos):
    hoja.append(["Metadato", "Valor"])
    for clave, valor in metadatos.items():
        hoja.append([clave, "" if valor is None else str(valor)])
    hoja.append([])


def respuesta_excel(libro, nombre):
    contenido = BytesIO()
    libro.save(contenido)
    respuesta = HttpResponse(contenido.getvalue(), content_type=CONTENT_TYPE_XLSX)
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta


def nuevo_libro(titulo, metadatos):
    libro = Workbook()
    hoja = libro.active
    hoja.title = titulo[:31]
    agregar_metadatos(hoja, metadatos)
    return libro, hoja
