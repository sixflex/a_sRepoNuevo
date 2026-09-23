from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from usuarios.decorators import coordinador_required
from .models import EnlacePlanificacion

# Flujo SP1
def coordinador_contexto(request):
    return render(request, 'proyectos/coordinador_contexto.html')

def formulario_prueba(request):
    return render(request, 'proyectos/formulario_prueba.html')


# SP2-T05: Gestión y Generación de Enlaces (Solo Coordinador)
@coordinador_required
def gestionar_enlaces_planificacion(request):
    if request.method == 'POST':
        destinatario_tipo = request.POST.get('destinatario_tipo')
        destinatario_nombre = request.POST.get('destinatario_nombre')
        destinatario_email = request.POST.get('destinatario_email')
        sede = request.POST.get('sede')
        campus = request.POST.get('campus')
        carrera = request.POST.get('carrera')
        periodo = request.POST.get('periodo')
        fecha_expiracion = request.POST.get('fecha_expiracion')

        if not (destinatario_tipo and destinatario_nombre and fecha_expiracion):
            messages.error(request, "Debe completar todos los campos obligatorios.")
        else:
            enlace = EnlacePlanificacion.objects.create(
                destinatario_tipo=destinatario_tipo,
                destinatario_nombre=destinatario_nombre,
                destinatario_email=destinatario_email,
                sede=sede,
                campus=campus,
                carrera=carrera,
                periodo=periodo,
                fecha_expiracion=fecha_expiracion,
                creado_por=request.user if request.user.is_authenticated else None
            )
            messages.success(request, f"Enlace generado exitosamente para {enlace.destinatario_nombre}.")
            return redirect('proyectos:gestionar_enlaces')

    enlaces = EnlacePlanificacion.objects.all()
    hoy = timezone.localdate().strftime('%Y-%m-%d')
    return render(request, 'proyectos/gestionar_enlaces.html', {
        'enlaces': enlaces,
        'hoy': hoy
    })


# SP2-T05: Acceso al Formulario por Enlace (Sin login requerido para Dirección/Secretaría)
def formulario_planificacion_docente(request, token):
    enlace = get_object_or_404(EnlacePlanificacion, id=token)

    context = {
        'enlace': enlace,
        'vigente': enlace.esta_vigente,
    }
    return render(request, 'proyectos/formulario_planificacion.html', context)