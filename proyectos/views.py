from django.shortcuts import render

def coordinador_contexto(request):
    # Configuracion contexto académico ficticio (SP1-T06)
    return render(request, 'proyectos/coordinador_contexto.html')

def formulario_prueba(request):
    # Formulario contextual demostrable y recepción de fila (SP1-T06)
    return render(request, 'proyectos/formulario_prueba.html')