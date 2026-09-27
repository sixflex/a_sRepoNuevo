from django.shortcuts import render
from .models import CargaPlanificacion, DetalleFilaObservada

def inicio(request):
    return render(request, 'base.html')

def validar_planificacion_view(request):
    resumen = None
    errores_filas = []

    if request.method == 'POST':
        enlace = request.POST.get('enlace_planificacion', '')
        unidad = request.POST.get('unidad', 'Departamento de Informática')
        periodo = request.POST.get('periodo', '2026-10')

        # Datos simulados de prueba
        filas_recibidas_raw = [
            {'fila': 1, 'nrc': '12345', 'asignatura': 'Programación Backend'},
            {'fila': 2, 'nrc': '12345', 'asignatura': 'Base de Datos'},  # Duplicado
            {'fila': 3, 'nrc': '67890', 'asignatura': 'Ingeniería de Software'},
            {'fila': 4, 'nrc': '', 'asignatura': ''},                    # Faltan obligatorios
            {'fila': 5, 'nrc': 'ABCDE', 'asignatura': 'Arquitectura Cloud'}, # Formato inválido
        ]

        nrcs_procesados = set()
        filas_aceptadas_list = []

        for item in filas_recibidas_raw:
            fila_num = item['fila']
            nrc = item['nrc'].strip() if item['nrc'] else ''
            asignatura = item['asignatura'].strip() if item['asignatura'] else ''

            causas = []

            # 1. Validación de obligatorios
            if not nrc or not asignatura:
                causas.append("Faltan campos obligatorios (NRC o Asignatura).")

            # 2. Validación de formatos
            if nrc and not nrc.isdigit():
                causas.append(f"El NRC '{nrc}' tiene un formato inválido (debe ser numérico).")

            # 3. Detección de NRC duplicado
            if nrc in nrcs_procesados and nrc != '':
                causas.append(f"NRC '{nrc}' duplicado en la misma entrega.")

            # 4. Separar filas válidas/observadas
            if causas:
                errores_filas.append({
                    'fila': fila_num,
                    'nrc': nrc if nrc else 'N/A',
                    'causa': " | ".join(causas)
                })
            else:
                filas_aceptadas_list.append(item)
                if nrc:
                    nrcs_procesados.add(nrc)

        # 5 y 7. Guardar resumen de recepción
        resumen = CargaPlanificacion.objects.create(
            unidad=unidad,
            periodo=periodo,
            filas_recibidas=len(filas_recibidas_raw),
            filas_aceptadas=len(filas_aceptadas_list),
            filas_observadas=len(errores_filas)
        )

        # 6. Registrar errores por fila en la base de datos
        for err in errores_filas:
            DetalleFilaObservada.objects.create(
                carga=resumen,
                numero_fila=err['fila'],
                nrc=err['nrc'],
                causa_error=err['causa']
            )

    # Si es GET pero queremos mostrar los errores de la última carga registrada:
    elif request.method == 'GET':
        resumen = CargaPlanificacion.objects.order_by('-id').first()
        if resumen:
            detalles_db = DetalleFilaObservada.objects.filter(carga=resumen)
            for d in detalles_db:
                errores_filas.append({
                    'fila': d.numero_fila,
                    'nrc': d.nrc,
                    'causa': d.causa_error
                })

    historial_cargas = CargaPlanificacion.objects.all().order_by('-id')

    return render(request, 'coordinacion/validar_planificacion.html', {
        'resumen': resumen,
        'errores_filas': errores_filas,
        'historial_cargas': historial_cargas
    })