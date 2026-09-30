from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.forms.utils import ErrorList
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import (DocenteFilaFormSet,FilaPlanificacionFormSet,)
from .models import (FilaPlanificacion,FilaPlanificacionDocente,Planificacion,PlanificacionEnlace,)
from .services import validar_y_consolidar_planificacion
from auditoria.services import registrar_auditoria

def _docentes_initial(fila):
    if not fila.pk:
        return []

    return [
        {
            "id": docente.id,
            "rut": docente.rut,
            "nombre": docente.nombre,
            "tipo_contrato": docente.tipo_contrato,
            "capacitado_as": docente.capacitado_as,
            "correo": docente.correo,
            "telefono": docente.telefono,
        }
        for docente in fila.docentes.all().order_by("id")
    ]


def _crear_formsets_docentes(request, formset_filas):
    formsets = []

    for indice, form_fila in enumerate(formset_filas.forms):
        prefix = f"docentes-{indice}"

        if request.method == "POST":
            formset_docentes = DocenteFilaFormSet(
                request.POST,
                prefix=prefix,
            )
        else:
            initial_data = _docentes_initial(form_fila.instance)
            extra_count = 1 if len(initial_data) == 0 else 0
            
            formset_docentes_class = DocenteFilaFormSet
            formset_docentes = formset_docentes_class(
                prefix=prefix,
                initial=initial_data,
            )
            if extra_count == 1:
                formset_docentes.extra = 1

        formsets.append(formset_docentes)

    return formsets


def _fila_esta_activa(form):
    cleaned = getattr(form, "cleaned_data", {})

    if not cleaned:
        return False

    if cleaned.get("DELETE"):
        return False

    campos = [
        cleaned.get("facultad_texto"),
        cleaned.get("carrera_texto"),
        cleaned.get("nrc"),
        cleaned.get("seccion"),
        cleaned.get("asignatura_texto"),
        cleaned.get("nivel"),
        cleaned.get("jornada"),
        cleaned.get("horario"),
        cleaned.get("estudiantes_planificados"),
    ]

    return any(
        valor not in (None, "")
        for valor in campos
    ) or cleaned.get("declaracion_as") is True


def _docente_tiene_datos(cleaned_data):
    if not cleaned_data or cleaned_data.get("DELETE"):
        return False

    campos = [
        cleaned_data.get("rut"),
        cleaned_data.get("nombre"),
        cleaned_data.get("tipo_contrato"),
        cleaned_data.get("correo"),
        cleaned_data.get("telefono"),
    ]

    return any(
        valor not in (None, "")
        for valor in campos
    ) or cleaned_data.get("capacitado_as") is not None


def _guardar_docentes(fila, formset_docentes):
    for form_docente in formset_docentes.forms:
        cleaned = getattr(form_docente, "cleaned_data", None)

        if not cleaned:
            continue

        docente_id = cleaned.get("id")

        if cleaned.get("DELETE"):
            if docente_id:
                fila.docentes.filter(pk=docente_id).delete()
            continue

        if not _docente_tiene_datos(cleaned):
            continue

        if docente_id:
            docente = get_object_or_404(
                fila.docentes,
                pk=docente_id,
            )
        else:
            docente = FilaPlanificacionDocente(
                fila=fila
            )

        docente.rut = cleaned.get("rut") or None
        docente.nombre = cleaned.get("nombre") or None
        docente.tipo_contrato = cleaned.get("tipo_contrato") or None
        docente.capacitado_as = cleaned.get("capacitado_as")
        docente.correo = cleaned.get("correo") or None
        docente.telefono = cleaned.get("telefono") or None
        docente.save()


def formulario_tabular_as(request, token):
    enlace = get_object_or_404(
        PlanificacionEnlace.objects.select_related(
            "unidad_academica",
            "unidad_academica__facultad",
            "unidad_academica__carrera",
            "campus__sede",
            "periodo",
        ),
        token=token,
    )

    vigente = (
        enlace.activo
        and (
            enlace.fecha_expiracion is None
            or enlace.fecha_expiracion >= timezone.now()
        )
    )

    planificacion_existente = Planificacion.objects.filter(
        enlace=enlace
    ).first()

    if not vigente and planificacion_existente is None:
        return render(
            request,
            "planificacion/formulario_tabular.html",
            {
                "enlace": enlace,
                "vigente": False,
                "editable": False,
                "hide_sidebar": True,
            },
        )

    planificacion, _ = Planificacion.objects.get_or_create(
        enlace=enlace,
        defaults={
            "estado": "BORRADOR",
            "filas_recibidas": 0,
            "filas_aceptadas": 0,
            "filas_observadas": 0,
        },
    )

    editable = vigente and planificacion.estado != "FINAL"

    queryset = (
        FilaPlanificacion.objects.filter(
            planificacion=planificacion
        )
        .prefetch_related("docentes", "errores")
        .order_by("numero_fila", "id")
    )

    if request.method == "POST":
        if not editable:
            messages.error(
                request,
                "Esta planificación no se puede modificar.",
            )
            return redirect(
                "planificacion:formulario_tabular_as",
                token=token,
            )

        formset = FilaPlanificacionFormSet(
            request.POST,
            queryset=queryset,
            prefix="filas",
        )
        docentes_formsets = _crear_formsets_docentes(
            request,
            formset,
        )

        formularios_validos = formset.is_valid()
        docentes_validos = True

        for form_fila, formset_docentes in zip(
            formset.forms,
            docentes_formsets,
        ):
            nrc_valor = getattr(form_fila, "cleaned_data", {}).get("nrc")
            if not _fila_esta_activa(form_fila) or not nrc_valor:
                continue

            if not formset_docentes.is_valid():
                docentes_validos = False
                continue

            docentes_utiles = [
                form_docente
                for form_docente in formset_docentes.forms
                if _docente_tiene_datos(
                    getattr(form_docente, "cleaned_data", {})
                )
            ]

            if not docentes_utiles:
                formset_docentes._non_form_errors = ErrorList(
                    ["Debe registrar al menos un Docente para esta fila."]
                )
                docentes_validos = False

        if formularios_validos and docentes_validos:
            estado_guardado = (
                "FINAL"
                if "enviar_final" in request.POST
                else "BORRADOR"
            )

            with transaction.atomic():
                for form_fila in formset.forms:
                    if (
                        getattr(form_fila, "cleaned_data", {}).get("DELETE")
                        and form_fila.instance.pk
                    ):
                        form_fila.instance.delete()

                max_numero = (
                    FilaPlanificacion.objects.filter(
                        planificacion=planificacion
                    ).aggregate(maximo=Max("numero_fila"))["maximo"]
                    or 0
                )

                for form_fila, formset_docentes in zip(
                    formset.forms,
                    docentes_formsets,
                ):
                    nrc_valor = getattr(form_fila, "cleaned_data", {}).get("nrc")
                    if not _fila_esta_activa(form_fila) or not nrc_valor:
                        continue

                    fila = form_fila.save(commit=False)
                    fila.planificacion = planificacion
                    fila.campus_texto = enlace.campus.nombre
                    fila.estado_validacion = "PENDIENTE"

                    if not fila.pk:
                        max_numero += 1
                        fila.numero_fila = max_numero

                    fila.save()
                    _guardar_docentes(
                        fila,
                        formset_docentes,
                    )

                planificacion.estado = estado_guardado
                planificacion.fecha_guardado = timezone.now()

                if estado_guardado == "FINAL":
                    planificacion.fecha_envio_final = timezone.now()

                planificacion.filas_recibidas = planificacion.filas.count()
                planificacion.filas_aceptadas = planificacion.filas.filter(
                    estado_validacion="ACEPTADA"
                ).count()
                planificacion.filas_observadas = planificacion.filas.filter(
                    estado_validacion="OBSERVADA"
                ).count()

                campos_actualizados = [
                    "estado",
                    "fecha_guardado",
                    "filas_recibidas",
                ]

                if estado_guardado == "FINAL":
                    campos_actualizados.append("fecha_envio_final")

                planificacion.save(update_fields=campos_actualizados)

                if estado_guardado == "FINAL":
                    validar_y_consolidar_planificacion(planificacion)

                    registrar_auditoria(
                        request=request,
                        entidad="Planificacion",
                        entidad_id=planificacion.id,
                        accion="ENVIO_FINAL_PLANIFICACION",
                        valores_nuevos={
                            "estado": planificacion.estado,
                            "filas_recibidas": planificacion.filas_recibidas,
                            "filas_aceptadas": planificacion.filas_aceptadas,
                            "filas_observadas": planificacion.filas_observadas,
                            "fecha_envio_final": (
                                planificacion.fecha_envio_final.isoformat()
                                if planificacion.fecha_envio_final
                                else None
                            ),
                        },
                        actor_externo=enlace.destinatario_correo,
                    )

            messages.success(
                request,
                "Planificación enviada correctamente."
                if estado_guardado == "FINAL"
                else "Borrador guardado correctamente.",
            )
            return redirect(
                "planificacion:formulario_tabular_as",
                token=token,
            )

    else:
        initial = []
        if not queryset.exists():
            unidad = enlace.unidad_academica
            facultad = (
                unidad.facultad
                or (
                    unidad.carrera.facultad
                    if unidad.carrera
                    else None
                )
            )
            initial.append(
                {
                    "facultad_texto": (
                        facultad.nombre
                        if facultad
                        else ""
                    ),
                    "carrera_texto": (
                        unidad.carrera.nombre
                        if unidad.carrera
                        else ""
                    ),
                    "posible_socio_texto": "",
                }
            )

        formset = FilaPlanificacionFormSet(
            queryset=queryset,
            prefix="filas",
            initial=initial,
        )
        if not queryset.exists():
            formset.extra = 1

        docentes_formsets = _crear_formsets_docentes(
            request,
            formset,
        )

    filas_con_docentes = list(
        zip(formset.forms, docentes_formsets)
    )

    return render(
        request,
        "planificacion/formulario_tabular.html",
        {
            "formset": formset,
            "filas_con_docentes": filas_con_docentes,
            "planificacion": planificacion,
            "enlace": enlace,
            "vigente": vigente,
            "editable": editable,
            "token": token,
            "hide_sidebar": True,
        },
    )