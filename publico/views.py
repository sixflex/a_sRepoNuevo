from django.contrib import messages
from django.shortcuts import redirect, render

from usuarios.decorators import coordinador_required

from . import portal


@coordinador_required
def configurar_portal(request):
    """Pestaña "Qué se muestra" de Portal público (RF-PUB-01)."""
    configuracion = portal.obtener_configuracion()
    errores = []

    if request.method == "POST":
        opciones, errores = portal.leer_formulario(request.POST)
        if not errores:
            portal.guardar_configuracion(opciones, request)
            messages.success(request, "Listo: el portal público ya muestra lo que elegiste.")
            return redirect("publico:configurar_portal")
        # Se vuelve a mostrar lo que marcó, sin perderlo (RNF-USA-02).
        configuracion.opciones_json = opciones

    return render(request, "publico/configurar_portal.html", {
        "bloques": portal.bloques_para_formulario(configuracion),
        "configuracion": configuracion,
        "errores": errores,
    })
