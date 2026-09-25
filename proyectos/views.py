from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from usuarios.decorators import coordinador_required
from planificacion.models import PlanificacionEnlace
from academico.models import Campus, Carrera, PeriodoAcademico

@coordinador_required
def coordinador_contexto(request):
    return render(request, 'proyectos/coordinador_contexto.html')

@coordinador_required
def formulario_prueba(request):
    return render(request, 'proyectos/formulario_prueba.html')

@coordinador_required
def gestionar_enlaces_planificacion(request):
    if request.method == 'POST':
        destinatario_tipo = request.POST.get('destinatario_tipo')
        destinatario_nombre = request.POST.get('destinatario_nombre')
        destinatario_correo = request.POST.get('destinatario_email')
        campus_id = request.POST.get('campus')
        carrera_id = request.POST.get('carrera')
        periodo_id = request.POST.get('periodo')
        fecha_vencimiento = request.POST.get('fecha_expiracion')

        if not all([
            destinatario_tipo,
            destinatario_nombre,
            destinatario_correo,
            campus_id,
            carrera_id,
            periodo_id,
            fecha_vencimiento,
        ]):
            messages.error(
                request,
                "Debe completar todos los campos obligatorios."
            )
        else:
            campus = get_object_or_404(Campus, pk=campus_id)
            carrera = get_object_or_404(Carrera, pk=carrera_id)
            periodo = get_object_or_404(PeriodoAcademico, pk=periodo_id)

            PlanificacionEnlace.objects.create(
                destinatario_tipo=destinatario_tipo,
                destinatario_nombre=destinatario_nombre,
                destinatario_correo=destinatario_correo,
                campus=campus,
                carrera=carrera,
                periodo=periodo,
                fecha_vencimiento=fecha_vencimiento,
            )

            messages.success(
                request,
                f"Enlace generado exitosamente para {destinatario_nombre}."
            )

            return redirect('proyectos:gestionar_enlaces')

    enlaces = (
        PlanificacionEnlace.objects
        .select_related('campus__sede', 'carrera', 'periodo')
        .order_by('-fecha_creacion')
    )

    campus = Campus.objects.filter(activo=True).select_related('sede')
    carreras = Carrera.objects.filter(activo=True)
    periodos = PeriodoAcademico.objects.all().order_by('-anio', 'tipo', 'nombre')

    hoy = timezone.localdate().strftime('%Y-%m-%d')

    return render(request, 'proyectos/gestionar_enlaces.html', {
        'enlaces': enlaces,
        'campus': campus,
        'carreras': carreras,
        'periodos': periodos,
        'hoy': hoy,
    })


def formulario_planificacion_docente(request, token):
    enlace = get_object_or_404(
        PlanificacionEnlace.objects.select_related(
            'campus__sede',
            'carrera',
            'periodo',
        ),
        token=token,
    )

    vigente = (
        enlace.activo
        and enlace.fecha_vencimiento >= timezone.now()
    )

    context = {
        'enlace': enlace,
        'vigente': vigente,
    }

    return render(
        request,
        'proyectos/formulario_planificacion.html',
        context,
    )