from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from .models import PlanificacionAS
from .forms import PlanificacionASFormSet

def formulario_tabular_as(request, token):
   
    registro_base = get_object_or_404(PlanificacionAS, token_acceso=token)
    carrera_contexto = registro_base.carrera

    queryset = PlanificacionAS.objects.filter(token_acceso=token)

    if request.method == 'POST':
        formset = PlanificacionASFormSet(request.POST, queryset=queryset)
        
        if formset.is_valid():
            estado_guardado = 'FINAL' if 'enviar_final' in request.POST else 'BORRADOR'
            
            with transaction.atomic():
            
                instancias = formset.save(commit=False)
                
                # 2. Guardar instancias modificadas/nuevas con sus datos contextuales
                for instancia in instancias:
                    instancia.carrera = carrera_contexto
                    instancia.token_acceso = token
                    instancia.estado_registro = estado_guardado
                    instancia.save()

                # 3. Eliminar físicamente las filas marcadas para borrar
                for obj in formset.deleted_objects:
                    obj.delete()

                # 4. Actualizar el estado de los registros existentes que no cambiaron
                # (Garantiza que al presionar 'Enviar Final' todo el lote cambie de estado)
                ids_eliminados = [obj.pk for obj in formset.deleted_objects if obj.pk]
                queryset.exclude(id__in=ids_eliminados).update(estado_registro=estado_guardado)

                formset.save_m2m()

            messages.success(request, f"Planificación guardada exitosamente como {estado_guardado}.")
            return redirect('planificacion:formulario_tabular_as', token=token)
    else:
        formset = PlanificacionASFormSet(queryset=queryset)

    return render(request, 'planificacion/formulario_tabular.html', {
        'formset': formset,
        'carrera': carrera_contexto,
        'token': token,
    })