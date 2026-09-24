from django.shortcuts import render, redirect, get_object_or_404
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import transaction

from usuarios.decorators import coordinador_required

from .models import (
    Sede,
    Campus,
    Facultad,
    Carrera,
    Asignatura,
    AsignaturaCarrera,
    Docente,
    PeriodoAcademico,
    Seccion,
    SeccionCarrera,
    SeccionDocente,
)


# =========================================================
# HOME
# =========================================================

@coordinador_required
def home(request):
    return render(request, "academico/home.html")


# =========================================================
# CRUD SEDES
# =========================================================

@coordinador_required
def sede_list(request):
    sedes = Sede.objects.all().order_by("nombre")

    return render(
        request,
        "academico/sede_list.html",
        {"sedes": sedes},
    )


@coordinador_required
def sede_create(request):
    error = None

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        ciudad = request.POST.get("ciudad", "").strip()

        if not nombre:
            error = "El nombre de la sede es obligatorio."

        elif Sede.objects.filter(nombre__iexact=nombre).exists():
            error = "Ya existe una sede con ese nombre."

        else:
            Sede.objects.create(
                nombre=nombre,
                ciudad=ciudad or None,
            )

            return redirect("sede_list")

    return render(
        request,
        "academico/sede_form.html",
        {
            "error": error,
        },
    )


@coordinador_required
def sede_list(request):
    sedes = Sede.objects.all().order_by("nombre")

    return render(
        request,
        "academico/sede_list.html",
        {"sedes": sedes},
    )


@coordinador_required
def sede_create(request):
    error = None

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        ciudad = request.POST.get("ciudad", "").strip()
        activo = request.POST.get("activo") == "on"

        if not nombre:
            error = "El nombre de la sede es obligatorio."

        elif Sede.objects.filter(nombre__iexact=nombre).exists():
            error = "Ya existe una sede con ese nombre."

        else:
            Sede.objects.create(
                nombre=nombre,
                ciudad=ciudad or None,
                activo=activo,
            )

            return redirect("sede_list")

    return render(
        request,
        "academico/sede_form.html",
        {
            "error": error,
        },
    )


@coordinador_required
def sede_update(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    error = None

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        ciudad = request.POST.get("ciudad", "").strip()
        activo = request.POST.get("activo") == "on"

        if not nombre:
            error = "El nombre de la sede es obligatorio."

        elif (
            Sede.objects
            .filter(nombre__iexact=nombre)
            .exclude(pk=sede.pk)
            .exists()
        ):
            error = "Ya existe otra sede con ese nombre."

        else:
            sede.nombre = nombre
            sede.ciudad = ciudad or None
            sede.activo = activo
            sede.save()

            return redirect("sede_list")

    return render(
        request,
        "academico/sede_form.html",
        {
            "sede": sede,
            "error": error,
        },
    )


@coordinador_required
def sede_delete(request, pk):
    sede = get_object_or_404(Sede, pk=pk)

    if request.method == "POST":
        sede.delete()
        return redirect("sede_list")

    return render(
        request,
        "academico/sede_delete.html",
        {
            "sede": sede,
        },
    )


# =========================================================
# CRUD CAMPUS
# =========================================================

@coordinador_required
def campus_list(request):
    campus = (
        Campus.objects
        .select_related("sede")
        .all()
        .order_by("sede__nombre", "nombre")
    )

    return render(
        request,
        "academico/campus_list.html",
        {"campus": campus},
    )


@coordinador_required
def campus_create(request):
    sedes = Sede.objects.filter(activo=True).order_by("nombre")
    error = None

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        direccion = request.POST.get("direccion", "").strip()
        sede_id = request.POST.get("sede")
        activo = request.POST.get("activo") == "on"

        if not nombre:
            error = "El nombre del campus es obligatorio."

        elif not sede_id:
            error = "Debes seleccionar una sede."

        else:
            sede = get_object_or_404(
                Sede,
                pk=sede_id,
                activo=True,
            )

            if Campus.objects.filter(
                sede=sede,
                nombre__iexact=nombre,
            ).exists():
                error = "Ya existe un campus con ese nombre en esta sede."

            else:
                Campus.objects.create(
                    sede=sede,
                    nombre=nombre,
                    direccion=direccion or None,
                    activo=activo,
                )

                return redirect("campus_list")

    return render(
        request,
        "academico/campus_form.html",
        {
            "sedes": sedes,
            "error": error,
        },
    )


@coordinador_required
def campus_update(request, pk):
    campus = get_object_or_404(Campus, pk=pk)

    # En edición mostramos todas las sedes para no perder
    # la relación si la sede actual está inactiva.
    sedes = Sede.objects.all().order_by("nombre")

    error = None

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        direccion = request.POST.get("direccion", "").strip()
        sede_id = request.POST.get("sede")
        activo = request.POST.get("activo") == "on"

        if not nombre:
            error = "El nombre del campus es obligatorio."

        elif not sede_id:
            error = "Debes seleccionar una sede."

        else:
            sede = get_object_or_404(Sede, pk=sede_id)

            repetido = (
                Campus.objects
                .filter(
                    sede=sede,
                    nombre__iexact=nombre,
                )
                .exclude(pk=campus.pk)
                .exists()
            )

            if repetido:
                error = "Ya existe otro campus con ese nombre en esta sede."

            else:
                campus.sede = sede
                campus.nombre = nombre
                campus.direccion = direccion or None
                campus.activo = activo
                campus.save()

                return redirect("campus_list")

    return render(
        request,
        "academico/campus_form.html",
        {
            "campus": campus,
            "sedes": sedes,
            "error": error,
        },
    )


@coordinador_required
def campus_delete(request, pk):
    campus = get_object_or_404(
        Campus.objects.select_related("sede"),
        pk=pk,
    )

    if request.method == "POST":
        campus.delete()
        return redirect("campus_list")

    return render(
        request,
        "academico/campus_confirm_delete.html",
        {
            "campus": campus,
        },
    )

# =========================================================
# CRUD FACULTADES
# =========================================================

@coordinador_required
def facultad_list(request):
    facultades = Facultad.objects.all().order_by("nombre")

    return render(
        request,
        "academico/facultad_list.html",
        {"facultades": facultades},
    )


@coordinador_required
def facultad_create(request):
    error = None

    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        activo = request.POST.get("activo") == "on"

        if not nombre:
            error = "El nombre de la facultad es obligatorio."

        elif codigo and Facultad.objects.filter(
            codigo__iexact=codigo
        ).exists():
            error = "Ya existe una facultad con ese código."

        else:
            Facultad.objects.create(
                codigo=codigo or None,
                nombre=nombre,
                activo=activo,
            )

            return redirect("facultad_list")

    return render(
        request,
        "academico/facultad_form.html",
        {
            "error": error,
        },
    )


@coordinador_required
def facultad_update(request, pk):
    facultad = get_object_or_404(Facultad, pk=pk)
    error = None

    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        activo = request.POST.get("activo") == "on"

        if not nombre:
            error = "El nombre de la facultad es obligatorio."

        elif (
            codigo
            and Facultad.objects
            .filter(codigo__iexact=codigo)
            .exclude(pk=facultad.pk)
            .exists()
        ):
            error = "Ya existe otra facultad con ese código."

        else:
            facultad.codigo = codigo or None
            facultad.nombre = nombre
            facultad.activo = activo
            facultad.save()

            return redirect("facultad_list")

    return render(
        request,
        "academico/facultad_form.html",
        {
            "facultad": facultad,
            "error": error,
        },
    )


@coordinador_required
def facultad_delete(request, pk):
    facultad = get_object_or_404(Facultad, pk=pk)

    if request.method == "POST":
        facultad.delete()
        return redirect("facultad_list")

    return render(
        request,
        "academico/facultad_confirm_delete.html",
        {
            "facultad": facultad,
        },
    )

# =========================================================
# CRUD CARRERAS
# =========================================================

@coordinador_required
def carrera_list(request):
    carreras = (
        Carrera.objects
        .select_related("facultad")
        .all()
        .order_by("facultad__nombre", "nombre")
    )

    return render(
        request,
        "academico/carrera_list.html",
        {"carreras": carreras},
    )


@coordinador_required
def carrera_create(request):
    facultades = Facultad.objects.filter(activo=True).order_by("nombre")
    error = None

    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        facultad_id = request.POST.get("facultad")
        activo = request.POST.get("activo") == "on"

        if not nombre:
            error = "El nombre de la carrera es obligatorio."

        elif not facultad_id:
            error = "Debes seleccionar una facultad."

        elif codigo and Carrera.objects.filter(
            codigo__iexact=codigo
        ).exists():
            error = "Ya existe una carrera con ese código."

        else:
            facultad = get_object_or_404(
                Facultad,
                pk=facultad_id,
                activo=True,
            )

            Carrera.objects.create(
                codigo=codigo or None,
                nombre=nombre,
                facultad=facultad,
                activo=activo,
            )

            return redirect("carrera_list")

    return render(
        request,
        "academico/carrera_form.html",
        {
            "facultades": facultades,
            "error": error,
        },
    )


@coordinador_required
def carrera_update(request, pk):
    carrera = get_object_or_404(Carrera, pk=pk)

    # En edición mostramos todas para conservar correctamente
    # una relación existente aunque la facultad esté inactiva.
    facultades = Facultad.objects.all().order_by("nombre")

    error = None

    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        facultad_id = request.POST.get("facultad")
        activo = request.POST.get("activo") == "on"

        if not nombre:
            error = "El nombre de la carrera es obligatorio."

        elif not facultad_id:
            error = "Debes seleccionar una facultad."

        elif (
            codigo
            and Carrera.objects
            .filter(codigo__iexact=codigo)
            .exclude(pk=carrera.pk)
            .exists()
        ):
            error = "Ya existe otra carrera con ese código."

        else:
            facultad = get_object_or_404(
                Facultad,
                pk=facultad_id,
            )

            carrera.codigo = codigo or None
            carrera.nombre = nombre
            carrera.facultad = facultad
            carrera.activo = activo
            carrera.save()

            return redirect("carrera_list")

    return render(
        request,
        "academico/carrera_form.html",
        {
            "carrera": carrera,
            "facultades": facultades,
            "error": error,
        },
    )


@coordinador_required
def carrera_delete(request, pk):
    carrera = get_object_or_404(
        Carrera.objects.select_related("facultad"),
        pk=pk,
    )

    if request.method == "POST":
        carrera.delete()
        return redirect("carrera_list")

    return render(
        request,
        "academico/carrera_confirm_delete.html",
        {
            "carrera": carrera,
        },
    )

# =========================================================
# CRUD ASIGNATURAS
# =========================================================

@coordinador_required
def asignatura_list(request):
    asignaturas = (
        Asignatura.objects
        .prefetch_related("carreras")
        .order_by("nombre")
    )

    return render(
        request,
        "academico/asignatura_list.html",
        {
            "asignaturas": asignaturas,
        },
    )


@coordinador_required
def asignatura_create(request):
    carreras = Carrera.objects.filter(activo=True).order_by("nombre")
    error = None
    carreras_seleccionadas = []

    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        activo = request.POST.get("activo") == "on"

        # Relación N:M
        carrera_ids = request.POST.getlist("carreras")

        # Conservamos la selección si ocurre un error
        carreras_seleccionadas = [
            int(carrera_id)
            for carrera_id in carrera_ids
            if carrera_id.isdigit()
        ]

        if not nombre:
            error = "El nombre de la asignatura es obligatorio."

        elif not carrera_ids:
            error = "Debes seleccionar al menos una carrera."

        elif codigo and Asignatura.objects.filter(
            codigo__iexact=codigo
        ).exists():
            error = "Ya existe una asignatura con ese código."

        else:
            carreras_objetos = Carrera.objects.filter(
                pk__in=carrera_ids,
                activo=True,
            )

            if carreras_objetos.count() != len(set(carrera_ids)):
                error = "Una de las carreras seleccionadas no existe o está inactiva."

            else:
                with transaction.atomic():

                    asignatura = Asignatura.objects.create(
                        codigo=codigo or None,
                        nombre=nombre,
                        activo=activo,
                    )

                    AsignaturaCarrera.objects.bulk_create([
                        AsignaturaCarrera(
                            asignatura=asignatura,
                            carrera=carrera,
                        )
                        for carrera in carreras_objetos
                    ])

                return redirect("asignatura_list")

    return render(
        request,
        "academico/asignatura_form.html",
        {
            "carreras": carreras,
            "carreras_seleccionadas": carreras_seleccionadas,
            "error": error,
        },
    )


@coordinador_required
def asignatura_update(request, pk):
    asignatura = get_object_or_404(
        Asignatura.objects.prefetch_related("carreras"),
        pk=pk,
    )

    # En edición mostramos todas para conservar
    # correctamente asociaciones existentes.
    carreras = Carrera.objects.all().order_by("nombre")
    error = None

    # Selección actual de la asignatura
    carreras_seleccionadas = list(
        asignatura.carreras.values_list("id", flat=True)
    )

    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        activo = request.POST.get("activo") == "on"

        carrera_ids = request.POST.getlist("carreras")

        # Si hay error, mantenemos lo seleccionado por el usuario
        carreras_seleccionadas = [
            int(carrera_id)
            for carrera_id in carrera_ids
            if carrera_id.isdigit()
        ]

        if not nombre:
            error = "El nombre de la asignatura es obligatorio."

        elif not carrera_ids:
            error = "Debes seleccionar al menos una carrera."

        elif (
            codigo
            and Asignatura.objects
            .filter(codigo__iexact=codigo)
            .exclude(pk=asignatura.pk)
            .exists()
        ):
            error = "Ya existe otra asignatura con ese código."

        else:
            carreras_objetos = Carrera.objects.filter(
                pk__in=carrera_ids
            )

            if carreras_objetos.count() != len(set(carrera_ids)):
                error = "Una de las carreras seleccionadas no existe."

            else:
                with transaction.atomic():

                    asignatura.codigo = codigo or None
                    asignatura.nombre = nombre
                    asignatura.activo = activo
                    asignatura.save()

                    # Eliminamos las asociaciones anteriores
                    AsignaturaCarrera.objects.filter(
                        asignatura=asignatura
                    ).delete()

                    # Creamos las nuevas asociaciones
                    AsignaturaCarrera.objects.bulk_create([
                        AsignaturaCarrera(
                            asignatura=asignatura,
                            carrera=carrera,
                        )
                        for carrera in carreras_objetos
                    ])

                return redirect("asignatura_list")

    return render(
        request,
        "academico/asignatura_form.html",
        {
            "asignatura": asignatura,
            "carreras": carreras,
            "carreras_seleccionadas": carreras_seleccionadas,
            "error": error,
        },
    )


@coordinador_required
def asignatura_delete(request, pk):
    asignatura = get_object_or_404(
        Asignatura.objects.prefetch_related("carreras"),
        pk=pk,
    )

    if request.method == "POST":
        asignatura.delete()
        return redirect("asignatura_list")

    return render(
        request,
        "academico/asignatura_confirm_delete.html",
        {
            "asignatura": asignatura,
        },
    )


# =========================================================
# CRUD DOCENTES
# =========================================================

@coordinador_required
def docente_list(request):
    docentes = (
        Docente.objects
        .all()
        .order_by("apellidos", "nombres")
    )

    return render(
        request,
        "academico/docente_list.html",
        {
            "docentes": docentes,
        },
    )


@coordinador_required
def docente_create(request):
    error = None

    if request.method == "POST":
        rut = request.POST.get("rut", "").strip()
        nombres = request.POST.get("nombres", "").strip()
        apellidos = request.POST.get("apellidos", "").strip()
        correo = request.POST.get(
            "correo_institucional",
            ""
        ).strip()
        telefono = request.POST.get("telefono", "").strip()
        activo = request.POST.get("activo") == "on"

        # VALIDACIONES
        if not rut:
            error = "El RUT del docente es obligatorio."

        elif not nombres:
            error = "Los nombres del docente son obligatorios."

        elif not apellidos:
            error = "Los apellidos del docente son obligatorios."

        elif not correo:
            error = "El correo institucional es obligatorio."

        elif Docente.objects.filter(
            rut__iexact=rut
        ).exists():
            error = "Ya existe un docente con ese RUT."

        elif Docente.objects.filter(
            correo_institucional__iexact=correo
        ).exists():
            error = "Ya existe un docente con ese correo institucional."

        else:
            try:
                validate_email(correo)

                Docente.objects.create(
                    rut=rut,
                    nombres=nombres,
                    apellidos=apellidos,
                    correo_institucional=correo,
                    telefono=telefono or None,
                    activo=activo,
                )

                return redirect("docente_list")

            except ValidationError:
                error = "Ingresa un correo electrónico válido."

    return render(
        request,
        "academico/docente_form.html",
        {
            "error": error,
        },
    )


@coordinador_required
def docente_update(request, pk):
    docente = get_object_or_404(
        Docente,
        pk=pk,
    )

    error = None

    if request.method == "POST":
        rut = request.POST.get("rut", "").strip()
        nombres = request.POST.get("nombres", "").strip()
        apellidos = request.POST.get("apellidos", "").strip()
        correo = request.POST.get(
            "correo_institucional",
            ""
        ).strip()
        telefono = request.POST.get("telefono", "").strip()
        activo = request.POST.get("activo") == "on"

        # VALIDACIONES
        if not rut:
            error = "El RUT del docente es obligatorio."

        elif not nombres:
            error = "Los nombres del docente son obligatorios."

        elif not apellidos:
            error = "Los apellidos del docente son obligatorios."

        elif not correo:
            error = "El correo institucional es obligatorio."

        elif (
            Docente.objects
            .filter(rut__iexact=rut)
            .exclude(pk=docente.pk)
            .exists()
        ):
            error = "Ya existe otro docente con ese RUT."

        elif (
            Docente.objects
            .filter(correo_institucional__iexact=correo)
            .exclude(pk=docente.pk)
            .exists()
        ):
            error = "Ya existe otro docente con ese correo institucional."

        else:
            try:
                validate_email(correo)

                docente.rut = rut
                docente.nombres = nombres
                docente.apellidos = apellidos
                docente.correo_institucional = correo
                docente.telefono = telefono or None
                docente.activo = activo

                docente.save()

                return redirect("docente_list")

            except ValidationError:
                error = "Ingresa un correo electrónico válido."

    return render(
        request,
        "academico/docente_form.html",
        {
            "docente": docente,
            "error": error,
        },
    )


@coordinador_required
def docente_delete(request, pk):
    docente = get_object_or_404(
        Docente,
        pk=pk,
    )

    if request.method == "POST":
        docente.delete()

        return redirect("docente_list")

    return render(
        request,
        "academico/docente_confirm_delete.html",
        {
            "docente": docente,
        },
    )

# =========================================================
# CRUD PERIODOS ACADÉMICOS
# =========================================================

@coordinador_required
def periodo_list(request):
    periodos = (
        PeriodoAcademico.objects
        .all()
        .order_by("-anio", "tipo", "nombre")
    )

    return render(
        request,
        "academico/periodo_list.html",
        {
            "periodos": periodos,
        },
    )


@coordinador_required
def periodo_create(request):
    error = None

    tipos_validos = [
        "Primer semestre",
        "Segundo semestre",
    ]

    estados_validos = [
        "Planificado",
        "Activo",
        "Finalizado",
    ]

    if request.method == "POST":
        anio = request.POST.get("anio", "").strip()
        tipo = request.POST.get("tipo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        fecha_inicio = request.POST.get("fecha_inicio", "").strip()
        fecha_fin = request.POST.get("fecha_fin", "").strip()
        estado = request.POST.get("estado", "").strip()

        if not anio:
            error = "El año es obligatorio."

        elif not anio.isdigit():
            error = "El año debe ser un número válido."

        elif len(anio) != 4:
            error = "El año debe contener 4 dígitos."

        elif int(anio) < 2000 or int(anio) > 2100:
            error = "El año debe estar entre 2000 y 2100."

        elif tipo not in tipos_validos:
            error = "Debes seleccionar un tipo de período válido."

        elif not nombre:
            error = "El nombre del período es obligatorio."

        elif estado not in estados_validos:
            error = "Debes seleccionar un estado válido."

        elif (
            fecha_inicio
            and fecha_fin
            and fecha_fin < fecha_inicio
        ):
            error = (
                "La fecha de término no puede ser "
                "anterior a la fecha de inicio."
            )

        elif PeriodoAcademico.objects.filter(
            anio=int(anio),
            tipo=tipo,
            nombre__iexact=nombre,
        ).exists():
            error = (
                "Ya existe un período académico con "
                "ese año, tipo y nombre."
            )

        else:
            PeriodoAcademico.objects.create(
                anio=int(anio),
                tipo=tipo,
                nombre=nombre,
                fecha_inicio=fecha_inicio or None,
                fecha_fin=fecha_fin or None,
                estado=estado,
            )

            return redirect("periodo_list")

    return render(
        request,
        "academico/periodo_form.html",
        {
            "error": error,
        },
    )


@coordinador_required
def periodo_update(request, pk):
    periodo = get_object_or_404(
        PeriodoAcademico,
        pk=pk,
    )

    error = None

    tipos_validos = [
        "Primer semestre",
        "Segundo semestre",
    ]

    estados_validos = [
        "Planificado",
        "Activo",
        "Finalizado",
    ]

    if request.method == "POST":
        anio = request.POST.get("anio", "").strip()
        tipo = request.POST.get("tipo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        fecha_inicio = request.POST.get("fecha_inicio", "").strip()
        fecha_fin = request.POST.get("fecha_fin", "").strip()
        estado = request.POST.get("estado", "").strip()

        if not anio:
            error = "El año es obligatorio."

        elif not anio.isdigit():
            error = "El año debe ser un número válido."

        elif len(anio) != 4:
            error = "El año debe contener 4 dígitos."

        elif int(anio) < 2000 or int(anio) > 2100:
            error = "El año debe estar entre 2000 y 2100."

        elif tipo not in tipos_validos:
            error = "Debes seleccionar un tipo de período válido."

        elif not nombre:
            error = "El nombre del período es obligatorio."

        elif estado not in estados_validos:
            error = "Debes seleccionar un estado válido."

        elif (
            fecha_inicio
            and fecha_fin
            and fecha_fin < fecha_inicio
        ):
            error = (
                "La fecha de término no puede ser "
                "anterior a la fecha de inicio."
            )

        elif (
            PeriodoAcademico.objects
            .filter(
                anio=int(anio),
                tipo=tipo,
                nombre__iexact=nombre,
            )
            .exclude(pk=periodo.pk)
            .exists()
        ):
            error = (
                "Ya existe otro período académico con "
                "ese año, tipo y nombre."
            )

        else:
            periodo.anio = int(anio)
            periodo.tipo = tipo
            periodo.nombre = nombre
            periodo.fecha_inicio = fecha_inicio or None
            periodo.fecha_fin = fecha_fin or None
            periodo.estado = estado

            periodo.save()

            return redirect("periodo_list")

    return render(
        request,
        "academico/periodo_form.html",
        {
            "periodo": periodo,
            "error": error,
        },
    )


@coordinador_required
def periodo_delete(request, pk):
    periodo = get_object_or_404(
        PeriodoAcademico,
        pk=pk,
    )

    if request.method == "POST":
        periodo.delete()

        return redirect("periodo_list")

    return render(
        request,
        "academico/periodo_confirm_delete.html",
        {
            "periodo": periodo,
        },
    )

# =========================================================
# CRUD SECCIONES / NRC
# =========================================================

@coordinador_required
def seccion_list(request):
    secciones = (
        Seccion.objects
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .prefetch_related(
            "carreras",
            "docentes",
        )
        .order_by(
            "-periodo__anio",
            "asignatura__nombre",
            "nrc",
        )
    )

    return render(
        request,
        "academico/seccion_list.html",
        {
            "secciones": secciones,
        },
    )


@coordinador_required
def seccion_create(request):
    asignaturas = (
        Asignatura.objects
        .filter(activo=True)
        .order_by("nombre")
    )

    docentes = (
        Docente.objects
        .filter(activo=True)
        .order_by("apellidos", "nombres")
    )

    periodos = (
        PeriodoAcademico.objects
        .all()
        .order_by("-anio", "tipo", "nombre")
    )

    campus_list = (
        Campus.objects
        .filter(activo=True)
        .select_related("sede")
        .order_by("sede__nombre", "nombre")
    )

    carreras = (
        Carrera.objects
        .filter(activo=True)
        .order_by("nombre")
    )

    error = None

    carreras_seleccionadas = []
    docentes_seleccionados = []

    if request.method == "POST":

        nrc = request.POST.get("nrc", "").strip()
        numero_seccion = request.POST.get("seccion", "").strip()

        asignatura_id = request.POST.get("asignatura")
        periodo_id = request.POST.get("periodo")
        campus_id = request.POST.get("campus")

        jornada = request.POST.get("jornada", "").strip()
        horario = request.POST.get("horario", "").strip()
        estado = request.POST.get("estado", "").strip()

        docente_ids = request.POST.getlist("docentes")
        carrera_ids = request.POST.getlist("carreras")

        # Mantiene las selecciones si ocurre un error.
        docentes_seleccionados = [
            int(docente_id)
            for docente_id in docente_ids
            if docente_id.isdigit()
        ]

        carreras_seleccionadas = [
            int(carrera_id)
            for carrera_id in carrera_ids
            if carrera_id.isdigit()
        ]

        if not nrc:
            error = "El NRC es obligatorio."

        elif not numero_seccion:
            error = "El número o código de sección es obligatorio."

        elif not periodo_id:
            error = "Debes seleccionar un período académico."

        elif not campus_id:
            error = "Debes seleccionar un campus."

        elif not asignatura_id:
            error = "Debes seleccionar una asignatura."

        elif not carrera_ids:
            error = "Debes seleccionar al menos una carrera."

        elif not docente_ids:
            error = "Debes seleccionar al menos un docente."

        elif not estado:
            error = "El estado de la sección es obligatorio."

        elif (
            Seccion.objects
            .filter(
                periodo_id=periodo_id,
                nrc=nrc,
            )
            .exists()
        ):
            error = (
                "Ya existe una sección con este NRC "
                "en el período seleccionado."
            )

        else:

            asignatura = get_object_or_404(
                Asignatura,
                pk=asignatura_id,
                activo=True,
            )

            periodo = get_object_or_404(
                PeriodoAcademico,
                pk=periodo_id,
            )

            campus_obj = get_object_or_404(
                Campus,
                pk=campus_id,
                activo=True,
            )

            docentes_objetos = Docente.objects.filter(
                pk__in=docente_ids,
                activo=True,
            )

            carreras_objetos = Carrera.objects.filter(
                pk__in=carrera_ids,
                activo=True,
            )

            if (
                docentes_objetos.count()
                != len(set(docente_ids))
            ):
                error = (
                    "Uno de los docentes seleccionados "
                    "no existe o está inactivo."
                )

            elif (
                carreras_objetos.count()
                != len(set(carrera_ids))
            ):
                error = (
                    "Una de las carreras seleccionadas "
                    "no existe o está inactiva."
                )

            else:

                with transaction.atomic():

                    seccion = Seccion.objects.create(
                        periodo=periodo,
                        campus=campus_obj,
                        asignatura=asignatura,
                        nrc=nrc,
                        seccion=numero_seccion,
                        jornada=jornada or None,
                        horario=horario or None,
                        estado=estado,
                    )

                    SeccionDocente.objects.bulk_create(
                        [
                            SeccionDocente(
                                seccion=seccion,
                                docente=docente,
                            )
                            for docente in docentes_objetos
                        ]
                    )

                    SeccionCarrera.objects.bulk_create(
                        [
                            SeccionCarrera(
                                seccion=seccion,
                                carrera=carrera,
                            )
                            for carrera in carreras_objetos
                        ]
                    )

                return redirect("seccion_list")

    return render(
        request,
        "academico/seccion_form.html",
        {
            "asignaturas": asignaturas,
            "docentes": docentes,
            "periodos": periodos,
            "campus_list": campus_list,
            "carreras": carreras,
            "carreras_seleccionadas": carreras_seleccionadas,
            "docentes_seleccionados": docentes_seleccionados,
            "error": error,
        },
    )


@coordinador_required
def seccion_update(request, pk):
    seccion = get_object_or_404(
        Seccion.objects.prefetch_related(
            "carreras",
            "docentes",
        ),
        pk=pk,
    )

    # En edición mostramos todos para no perder
    # relaciones antiguas si algún registro quedó inactivo.
    asignaturas = Asignatura.objects.all().order_by("nombre")

    docentes = (
        Docente.objects
        .all()
        .order_by("apellidos", "nombres")
    )

    periodos = (
        PeriodoAcademico.objects
        .all()
        .order_by("-anio", "tipo", "nombre")
    )

    campus_list = (
        Campus.objects
        .select_related("sede")
        .all()
        .order_by("sede__nombre", "nombre")
    )

    carreras = (
        Carrera.objects
        .all()
        .order_by("nombre")
    )

    error = None

    carreras_seleccionadas = list(
        seccion.carreras.values_list(
            "id",
            flat=True,
        )
    )

    docentes_seleccionados = list(
        seccion.docentes.values_list(
            "id",
            flat=True,
        )
    )

    if request.method == "POST":

        nrc = request.POST.get("nrc", "").strip()
        numero_seccion = request.POST.get("seccion", "").strip()

        asignatura_id = request.POST.get("asignatura")
        periodo_id = request.POST.get("periodo")
        campus_id = request.POST.get("campus")

        jornada = request.POST.get("jornada", "").strip()
        horario = request.POST.get("horario", "").strip()
        estado = request.POST.get("estado", "").strip()

        docente_ids = request.POST.getlist("docentes")
        carrera_ids = request.POST.getlist("carreras")

        # Mantener selección en caso de error.
        docentes_seleccionados = [
            int(docente_id)
            for docente_id in docente_ids
            if docente_id.isdigit()
        ]

        carreras_seleccionadas = [
            int(carrera_id)
            for carrera_id in carrera_ids
            if carrera_id.isdigit()
        ]

        if not nrc:
            error = "El NRC es obligatorio."

        elif not numero_seccion:
            error = "El número o código de sección es obligatorio."

        elif not periodo_id:
            error = "Debes seleccionar un período académico."

        elif not campus_id:
            error = "Debes seleccionar un campus."

        elif not asignatura_id:
            error = "Debes seleccionar una asignatura."

        elif not carrera_ids:
            error = "Debes seleccionar al menos una carrera."

        elif not docente_ids:
            error = "Debes seleccionar al menos un docente."

        elif not estado:
            error = "El estado de la sección es obligatorio."

        elif (
            Seccion.objects
            .filter(
                periodo_id=periodo_id,
                nrc=nrc,
            )
            .exclude(pk=seccion.pk)
            .exists()
        ):
            error = (
                "Ya existe otra sección con este NRC "
                "en el período seleccionado."
            )

        else:

            asignatura = get_object_or_404(
                Asignatura,
                pk=asignatura_id,
            )

            periodo = get_object_or_404(
                PeriodoAcademico,
                pk=periodo_id,
            )

            campus_obj = get_object_or_404(
                Campus,
                pk=campus_id,
            )

            docentes_objetos = Docente.objects.filter(
                pk__in=docente_ids
            )

            carreras_objetos = Carrera.objects.filter(
                pk__in=carrera_ids
            )

            if (
                docentes_objetos.count()
                != len(set(docente_ids))
            ):
                error = (
                    "Uno de los docentes seleccionados "
                    "no existe."
                )

            elif (
                carreras_objetos.count()
                != len(set(carrera_ids))
            ):
                error = (
                    "Una de las carreras seleccionadas "
                    "no existe."
                )

            else:

                with transaction.atomic():

                    seccion.nrc = nrc
                    seccion.seccion = numero_seccion
                    seccion.asignatura = asignatura
                    seccion.periodo = periodo
                    seccion.campus = campus_obj
                    seccion.jornada = jornada or None
                    seccion.horario = horario or None
                    seccion.estado = estado

                    seccion.save()

                    # DOCENTES
                    SeccionDocente.objects.filter(
                        seccion=seccion
                    ).delete()

                    SeccionDocente.objects.bulk_create(
                        [
                            SeccionDocente(
                                seccion=seccion,
                                docente=docente,
                            )
                            for docente in docentes_objetos
                        ]
                    )

                    # CARRERAS
                    SeccionCarrera.objects.filter(
                        seccion=seccion
                    ).delete()

                    SeccionCarrera.objects.bulk_create(
                        [
                            SeccionCarrera(
                                seccion=seccion,
                                carrera=carrera,
                            )
                            for carrera in carreras_objetos
                        ]
                    )

                return redirect("seccion_list")

    return render(
        request,
        "academico/seccion_form.html",
        {
            "seccion": seccion,
            "asignaturas": asignaturas,
            "docentes": docentes,
            "periodos": periodos,
            "campus_list": campus_list,
            "carreras": carreras,
            "carreras_seleccionadas": carreras_seleccionadas,
            "docentes_seleccionados": docentes_seleccionados,
            "error": error,
        },
    )


@coordinador_required
def seccion_delete(request, pk):
    seccion = get_object_or_404(
        Seccion.objects
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .prefetch_related(
            "carreras",
            "docentes",
        ),
        pk=pk,
    )

    if request.method == "POST":
        seccion.delete()

        return redirect("seccion_list")

    return render(
        request,
        "academico/seccion_confirm_delete.html",
        {
            "seccion": seccion,
        },
    )


# =========================================================
# CONSULTA DE PLANIFICACIÓN ACADÉMICA
# =========================================================

@coordinador_required
def planificacion_list(request):
    secciones = (
        Seccion.objects
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .prefetch_related(
            "carreras",
            "carreras__facultad",
            "docentes",
        )
    )

    # -------------------------
    # FILTROS
    # -------------------------

    periodo_id = request.GET.get("periodo")
    carrera_id = request.GET.get("carrera")
    asignatura_id = request.GET.get("asignatura")
    docente_id = request.GET.get("docente")
    nrc = request.GET.get("nrc", "").strip()

    if periodo_id:
        secciones = secciones.filter(
            periodo_id=periodo_id
        )

    if carrera_id:
        secciones = secciones.filter(
            carreras__id=carrera_id
        )

    if asignatura_id:
        secciones = secciones.filter(
            asignatura_id=asignatura_id
        )

    if docente_id:
        secciones = secciones.filter(
            docentes__id=docente_id
        )

    if nrc:
        secciones = secciones.filter(
            nrc__icontains=nrc
        )

    # Las relaciones N:M pueden generar filas repetidas.
    secciones = (
        secciones
        .distinct()
        .order_by(
            "-periodo__anio",
            "periodo__tipo",
            "asignatura__nombre",
            "nrc",
        )
    )

    # -------------------------
    # OPCIONES DE LOS FILTROS
    # -------------------------

    periodos = (
        PeriodoAcademico.objects
        .all()
        .order_by(
            "-anio",
            "tipo",
            "nombre",
        )
    )

    carreras = (
        Carrera.objects
        .all()
        .order_by("nombre")
    )

    asignaturas = (
        Asignatura.objects
        .all()
        .order_by("nombre")
    )

    docentes = (
        Docente.objects
        .all()
        .order_by(
            "apellidos",
            "nombres",
        )
    )

    context = {
        "secciones": secciones,
        "periodos": periodos,
        "carreras": carreras,
        "asignaturas": asignaturas,
        "docentes": docentes,

        "filtros": {
            "periodo": periodo_id or "",
            "carrera": carrera_id or "",
            "asignatura": asignatura_id or "",
            "docente": docente_id or "",
            "nrc": nrc,
        },
    }

    return render(
        request,
        "academico/planificacion_list.html",
        context,
    )


@coordinador_required
def planificacion_detail(request, pk):
    seccion = get_object_or_404(
        Seccion.objects
        .select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        )
        .prefetch_related(
            "seccion_carreras__carrera",
            "seccion_carreras__carrera__facultad",
            "seccion_docentes__docente",
        ),
        pk=pk,
    )

    return render(
        request,
        "academico/planificacion_detail.html",
        {
            "seccion": seccion,
        },
    )