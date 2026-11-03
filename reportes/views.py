from django.shortcuts import render
from django.urls import reverse

from auditoria.services import registrar_auditoria
from core import excel, indicadores
from encuestas.models import FormularioVersion
from usuarios.decorators import coordinador_only_required

from . import services


@coordinador_only_required
def inicio(request):
    """Apartado Reportes: todos los Excel con los mismos filtros combinables."""
    filtros = services.leer_filtros(request.GET)
    parametros = request.GET.copy()
    parametros[indicadores.MARCA_FILTRADO] = "1"
    consulta = parametros.urlencode()

    formularios = (
        FormularioVersion.objects
        .filter(respuestas__isnull=False)
        .select_related("plantilla")
        .distinct()
        .order_by("plantilla__titulo", "-numero_version")
    )

    return render(request, "reportes/inicio.html", {
        "filtros": filtros,
        "chips": indicadores.chips(filtros),
        "opciones": indicadores.opciones_filtros(),
        "consulta": consulta,
        "url_indicadores": f"{reverse('core:exportar_indicadores')}?{consulta}",
        "formularios": formularios,
    })


def _descargar(request, accion, construir, nombre):
    filtros = services.leer_filtros(request.GET)
    libro = construir(filtros)
    registrar_auditoria(
        request=request, entidad="Reporte", entidad_id=accion.lower(),
        accion=accion, valores_nuevos={"filtros": {k: v for k, v in filtros.items() if v}},
    )
    return excel.respuesta_excel(libro, nombre)


@coordinador_only_required
def participaciones(request):
    return _descargar(request, "EXPORTAR_PARTICIPACIONES", services.libro_participaciones, "proyectos_y_participaciones.xlsx")


@coordinador_only_required
def centros_sercotec(request):
    return _descargar(request, "EXPORTAR_CENTROS_SERCOTEC", services.libro_centros_sercotec, "emprendedores_por_centro_sercotec.xlsx")
