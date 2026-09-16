from django.shortcuts import render

# Vistas del flujo demostrable académico (SP1-T06)
def coordinador_contexto(request):
    """Paso 1: Configurar contexto académico ficticio."""
    return render(request, 'proyectos/coordinador_contexto.html')

def formulario_prueba(request):
    """Paso 2 y 3: Formulario contextual demostrable y recepción de fila."""
    return render(request, 'proyectos/formulario_prueba.html')