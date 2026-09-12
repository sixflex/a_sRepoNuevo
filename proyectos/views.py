from django.shortcuts import render

# Vistas de la tarea SP1-T06
def coordinador_contexto(request):
    # Configuracion contexto académico ficticio
    return render(request, 'proyectos/coordinador_contexto.html')

def formulario_prueba(request):
    # Formulario contextual demostrable y recepción de fila
    return render(request, 'proyectos/formulario_prueba.html')