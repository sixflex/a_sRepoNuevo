from datetime import date, datetime
from io import BytesIO

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


CONTENT_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Colores del portal (rojo UA) para los encabezados.
ROJO_UA = "C8232C"
GRIS_CLARO = "F3F4F6"
ANCHO_MAXIMO = 60


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


def _vacia(hoja, fila):
    return all(celda.value in (None, "") for celda in hoja[fila])


def _tablas(hoja):
    """
    (encabezado, última fila) de cada tabla de la hoja. Las tablas van
    separadas por una fila vacía; el bloque de metadatos no cuenta.
    """
    fila = 1
    if hoja.max_row and hoja["A1"].value == "Metadato":
        while fila <= hoja.max_row and not _vacia(hoja, fila):
            fila += 1
    tablas = []
    while fila <= hoja.max_row:
        if _vacia(hoja, fila):
            fila += 1
            continue
        inicio = fila
        while fila <= hoja.max_row and not _vacia(hoja, fila):
            fila += 1
        tablas.append((inicio, fila - 1))
    return tablas


def dar_formato(libro):
    """
    Deja cada hoja ordenada y fácil de usar: metadatos en gris, encabezados en
    rojo UA, filtros desplegables en la primera tabla (para filtrar por año,
    sede, carrera... dentro del mismo Excel), encabezado fijo al bajar y
    columnas con un ancho según su contenido.
    """
    borde = Border(bottom=Side(style="thin", color="D1D5DB"))
    for hoja in libro.worksheets:
        if not hoja.max_row:
            continue
        if hoja["A1"].value == "Metadato":
            for fila in hoja.iter_rows(min_row=1, max_col=2):
                if _vacia(hoja, fila[0].row):
                    break
                for celda in fila:
                    celda.fill = PatternFill("solid", fgColor=GRIS_CLARO)
                fila[0].font = Font(bold=True, color="374151")
            hoja["A1"].font = hoja["B1"].font = Font(bold=True, color="6B7280", size=9)

        tablas = _tablas(hoja)
        for indice, (encabezado, ultima) in enumerate(tablas):
            for celda in hoja[encabezado]:
                if celda.value in (None, ""):
                    continue
                celda.font = Font(bold=True, color="FFFFFF")
                celda.fill = PatternFill("solid", fgColor=ROJO_UA)
                celda.alignment = Alignment(vertical="center", wrap_text=True)
            hoja.row_dimensions[encabezado].height = 30
            for fila in hoja.iter_rows(min_row=encabezado + 1, max_row=ultima):
                for celda in fila:
                    celda.border = borde
                    if isinstance(celda.value, datetime):
                        celda.number_format = "dd/mm/yyyy hh:mm"
                    elif isinstance(celda.value, date):
                        celda.number_format = "dd/mm/yyyy"
                    elif isinstance(celda.value, str) and len(celda.value) > ANCHO_MAXIMO:
                        celda.alignment = Alignment(wrap_text=True, vertical="top")
            if indice == 0:
                columnas = hoja.max_column
                hoja.freeze_panes = hoja.cell(encabezado + 1, 1)
                if ultima > encabezado:
                    # Excel permite un solo filtro por hoja: va en la tabla principal.
                    hoja.auto_filter.ref = f"A{encabezado}:{get_column_letter(columnas)}{ultima}"

        for columna in hoja.iter_cols(min_row=1, max_row=hoja.max_row):
            largo = max((len(str(celda.value)) for celda in columna if celda.value not in (None, "")), default=0)
            letra = get_column_letter(columna[0].column)
            hoja.column_dimensions[letra].width = max(10, min(ANCHO_MAXIMO, largo + 3))


def respuesta_excel(libro, nombre):
    dar_formato(libro)
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
