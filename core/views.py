from django.shortcuts import render
from .models import CargaPlanificacion, DetalleFilaObservada

def inicio(request):
    """
    Vista principal para renderizar la página de inicio/dashboard.
    """
    return render(request, 'core/inicio.html')

def validar_planificacion_view(request):
    """
    Vista que implementa RF-ACA-04: Validación de planificación por enlace,
    detección de errores por fila y registro del resumen para Coordinación.
    """
    resumen = None
    errores_filas = []

    if request.method == 'POST':
        enlace = request.POST.get('enlace_planificacion', '')
        unidad = request.POST.get('unidad', 'Departamento de Informática')
        periodo = request.POST.get('periodo', '2026-10')

        # Simulamos las filas que vendrían desde el enlace recibido
        filas_recibidas_raw = [
            {'fila': 1, 'nrc': '1001', 'asignatura': 'Matemáticas', 'docente': 'Juan Pérez'},
            {'fila': 2, 'nrc': '', 'asignatura': 'Historia', 'docente': 'María López'}, # Error: Falta NRC
            {'fila': 3, 'nrc': '1001', 'asignatura': 'Física', 'docente': 'Carlos Ruíz'}, # Error: NRC Duplicado
            {'fila': 4, 'nrc': 'ABC-99', 'asignatura': 'Química', 'docente': 'Ana Gómez'}, # Error: Formato no numérico
            {'fila': 5, 'nrc': '1004', 'asignatura': 'Programación', 'docente': 'Pedro Soto'}, # VÁLIDO
        ]

        total_recibidas = len(filas_recibidas_raw)
        filas_aceptadas_list = []
        nrcs_procesados = set()

        for item in filas_recibidas_raw:
            num_fila = item['fila']
            nrc = str(item['nrc']).strip()
            asignatura = item.get('asignatura', '').strip()
            
            causas = []

            # Rule 1: Campos obligatorios
            if not nrc or not asignatura:
                causas.append("Faltan campos obligatorios (NRC o Asignatura).")

            # Rule 2: Formato del NRC (debe ser numérico)
            if nrc and not nrc.isdigit():
                causas.append(f"El NRC '{nrc}' tiene un formato inválido (debe ser numérico).")

            # Rule 3: Duplicidad de NRC
            if nrc in nrcs_procesados and nrc != '':
                causas.append(f"NRC '{nrc}' duplicado en la misma entrega.")

            if causas:
                errores_filas.append({
                    'fila': num_fila,
                    'nrc': nrc or 'N/A',
                    'causa': ' | '.join(causas)
                })
            else:
                nrcs_procesados.add(nrc)
                filas_aceptadas_list.append(item)

        # Crear el resumen en la Base de Datos
        resumen = CargaPlanificacion.objects.create(
            unidad=unidad,
            periodo=periodo,
            enlace_origen=enlace,
            filas_recibidas=total_recibidas,
            filas_aceptadas=len(filas_aceptadas_list),
            filas_observadas=len(errores_filas)
        )

        # Guardar las observaciones específicas
        for err in errores_filas:
            DetalleFilaObservada.objects.create(
                carga=resumen,
                numero_fila=err['fila'],
                nrc=err['nrc'],
                causa_error=err['causa']
            )

    historial_cargas = CargaPlanificacion.objects.all().order_by('-fecha')

    return render(request, 'coordinacion/validar_planificacion.html', {
        'resumen': resumen,
        'errores_filas': errores_filas,
        'historial_cargas': historial_cargas
    })