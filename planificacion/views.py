from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import FilaPlanificacionFormSet
from .models import (
    FilaPlanificacion,
    Planificacion,
    PlanificacionEnlace,
)

def formulario_tabular_as(request, token):
    enlace = get_object_or_404(
        PlanificacionEnlace.objects.select_related(
            "campus__sede",
            "carrera",
            "periodo",
        ),
        token=token,
    )

    vigente = (
        enlace.activo
        and enlace.fecha_vencimiento >= timezone.now()
    )

    if not vigente:
        return render(
            request,
            "planificacion/formulario_tabular.html",
            {
                "enlace": enlace,
                "vigente": False,
            },
        )

    planificacion, _ = Planificacion.objects.get_or_create(
        enlace=enlace,
        defaults={
            "campus": enlace.campus,
            "periodo": enlace.periodo,
            "unidad_carrera": enlace.carrera,
            "destinatario_correo": enlace.destinatario_correo,
            "vence_en": enlace.fecha_vencimiento,
            "estado": "BORRADOR",
        },
    )

    queryset = FilaPlanificacion.objects.filter(
        planificacion=planificacion
    ).order_by("id")

    if request.method == "POST":
        formset = FilaPlanificacionFormSet(
            request.POST,
            queryset=queryset,
        )

        if formset.is_valid():
            estado_guardado = (
                "FINAL"
                if "enviar_final" in request.POST
                else "BORRADOR"
            )

            with transaction.atomic():
                instancias = formset.save(commit=False)

                for instancia in instancias:
                    instancia.planificacion = planificacion
                    instancia.save()

                for obj in formset.deleted_objects:
                    obj.delete()

                planificacion.estado = estado_guardado

                if estado_guardado == "FINAL":
                    planificacion.fecha_envio = timezone.now()

                planificacion.save(
                    update_fields=[
                        "estado",
                        "fecha_envio",
                    ]
                )

            if estado_guardado == "FINAL":
                messages.success(
                    request,
                    "Planificación enviada correctamente.",
                )
            else:
                messages.success(
                    request,
                    "Borrador guardado correctamente.",
                )

            return redirect(
                "planificacion:formulario_tabular_as",
                token=token,
            )

    else:
        formset = FilaPlanificacionFormSet(
            queryset=queryset
        )

    return render(
        request,
        "planificacion/formulario_tabular.html",
        {
            "formset": formset,
            "planificacion": planificacion,
            "enlace": enlace,
            "carrera": enlace.carrera,
            "vigente": True,
            "token": token,
        },
    )