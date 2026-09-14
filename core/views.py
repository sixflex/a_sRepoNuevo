from django.shortcuts import render

def coordinacion_view(request):
    contexto = {
        'show_sidebar_toggle': True,
        'mensaje_prueba': '¡Django está conectado y funcionando perfectamente!'
    }
    return render(request, 'layouts/layout_coordinacion.html', contexto)