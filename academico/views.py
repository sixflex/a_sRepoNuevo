from collections import Counter

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import render, redirect, get_object_or_404

from core.validators import validar_rut_chileno
from . import constantes
from .services import codigo_unico, nombre_repetido, normalizar_codigo
from usuarios.decorators import coordinador_required

from .models import (
    Sede,
    Campus,
    Facultad,
    Carrera,
    UnidadAcademica,
    Asignatura,
    AsignaturaCarrera,
    Docente,
    PeriodoAcademico,
    Seccion,
    SeccionCarrera,
    SeccionDocente,
)


# =========================================================
# UTILIDADES COMUNES
# =========================================================
#
# Criterio para los 9 CRUD:
# - Crear y editar comparten una sola función por entidad (_guardar_*).
# - Los datos enviados se copian al objeto ANTES de validar. Si hay un
#   error, el formulario se vuelve a mostrar con lo que escribió el
#   usuario (RNF-USA-02) y el objeto no se guarda.
# - Eliminar nunca da error 500: si hay datos asociados se avisa.

# Nombres en español de los registros que pueden impedir un borrado.
NOMBRES_RELACIONADOS = {
    "academico.Campus": ("campus", "campus"),
    "academico.Carrera": ("carrera", "carreras"),
    "academico.Seccion": ("sección", "secciones"),
    "planificacion.PlanificacionEnlace": (
        "enlace de planificación",
        "enlaces de planificación",
    ),
    "cartas.SolicitudCarta": ("solicitud de carta", "solicitudes de carta"),
    "proyectos.Equipo": ("equipo", "equipos"),
    "proyectos.EnlaceRegistroEquipo": (
        "enlace de registro de equipos",
        "enlaces de registro de equipos",
    ),
    "proyectos.IntegranteEtiqueta": ("etiqueta asignada", "etiquetas asignadas"),
}


def _texto_relacionados(protegidos):
    conteo = Counter(objeto._meta.label for objeto in protegidos)
    partes = []

    for etiqueta, cantidad in conteo.items():
        singular, plural = NOMBRES_RELACIONADOS.get(
            etiqueta,
            ("registro asociado", "registros asociados"),
        )
        partes.append(f"{cantidad} {singular if cantidad == 1 else plural}")

    if len(partes) > 1:
        return ", ".join(partes[:-1]) + " y " + partes[-1]

    return partes[0]


def _eliminar(request, objeto, url_lista):
    """
    Elimina el objeto y vuelve al listado. Si otros registros lo usan
    (on_delete=PROTECT) muestra un mensaje claro en vez de un error 500.
    """
    nombre = str(objeto)

    try:
        objeto.delete()

    except ProtectedError as error:
        mensaje = (
            f"No se puede eliminar «{nombre}»: tiene registros asociados "
            f"({_texto_relacionados(error.protected_objects)})."
        )

        if hasattr(objeto, "activo"):
            mensaje += " Desactive el registro en su lugar."
        else:
            mensaje += " Elimine o reasigne primero esos registros."

        messages.error(request, mensaje)

    else:
        messages.success(request, f"«{nombre}» fue eliminado.")

    return redirect(url_lista)


def _contexto_codigo(modelo, objeto):
    """
    Datos para que el JS del formulario sugiera el código mientras se
    escribe el nombre (solo al crear; al editar se respeta el guardado).
    """
    if objeto.pk:
        return {}

    return {
        "codigos_usados": [
            codigo.upper()
            for codigo in modelo.objects
            .exclude(codigo__isnull=True)
            .values_list("codigo", flat=True)
        ],
        "palabras_sin_inicial": sorted(constantes.PALABRAS_SIN_INICIAL),
        "largo_codigo": constantes.LARGO_CODIGO_SUGERIDO,
    }


def _ids_seleccionados(valores):
    """Convierte los id de un <select multiple> a enteros para la plantilla."""
    return [
        int(valor)
        for valor in valores
        if valor.isdigit()
    ]


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


def _guardar_sede(request, sede):
    error = None

    if request.method == "POST":
        sede.nombre = request.POST.get("nombre", "").strip()
        sede.ciudad = request.POST.get("ciudad", "").strip() or None
        sede.activo = request.POST.get("activo") == "on"

        if not sede.nombre:
            error = "El nombre de la sede es obligatorio."

        elif (
            Sede.objects
            .filter(nombre__iexact=sede.nombre)
            .exclude(pk=sede.pk)
            .exists()
        ):
            error = "Ya existe una sede con ese nombre."

        else:
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
def sede_create(request):
    return _guardar_sede(request, Sede(activo=True))


@coordinador_required
def sede_update(request, pk):
    return _guardar_sede(request, get_object_or_404(Sede, pk=pk))


@coordinador_required
def sede_delete(request, pk):
    sede = get_object_or_404(Sede, pk=pk)

    if request.method == "POST":
        return _eliminar(request, sede, "sede_list")

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


def _guardar_campus(request, campus):
    es_nuevo = campus.pk is None

    # Al crear solo se ofrecen sedes activas. En edición mostramos todas
    # para no perder la relación si la sede actual está inactiva.
    sedes = Sede.objects.all().order_by("nombre")
    if es_nuevo:
        sedes = sedes.filter(activo=True)

    error = None

    if request.method == "POST":
        campus.nombre = request.POST.get("nombre", "").strip()
        campus.direccion = request.POST.get("direccion", "").strip() or None
        campus.activo = request.POST.get("activo") == "on"
        sede_id = request.POST.get("sede")

        if sede_id:
            campus.sede = get_object_or_404(sedes, pk=sede_id)

        if not campus.nombre:
            error = "El nombre del campus es obligatorio."

        elif not sede_id:
            error = "Debes seleccionar una sede."

        elif (
            Campus.objects
            .filter(
                sede=campus.sede,
                nombre__iexact=campus.nombre,
            )
            .exclude(pk=campus.pk)
            .exists()
        ):
            error = "Ya existe un campus con ese nombre en esta sede."

        else:
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
def campus_create(request):
    return _guardar_campus(request, Campus(activo=True))


@coordinador_required
def campus_update(request, pk):
    return _guardar_campus(request, get_object_or_404(Campus, pk=pk))


@coordinador_required
def campus_delete(request, pk):
    campus = get_object_or_404(
        Campus.objects.select_related("sede"),
        pk=pk,
    )

    if request.method == "POST":
        return _eliminar(request, campus, "campus_list")

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


def _guardar_facultad(request, facultad):
    error = None

    if request.method == "POST":
        facultad.codigo = normalizar_codigo(request.POST.get("codigo")) or None
        facultad.nombre = request.POST.get("nombre", "").strip()
        facultad.activo = request.POST.get("activo") == "on"

        if not facultad.nombre:
            error = "El nombre de la facultad es obligatorio."

        elif nombre_repetido(Facultad.objects, facultad.nombre, facultad.pk):
            error = "Ya existe una facultad con ese nombre."

        elif (
            facultad.codigo
            and Facultad.objects
            .filter(codigo__iexact=facultad.codigo)
            .exclude(pk=facultad.pk)
            .exists()
        ):
            error = "Ya existe una facultad con ese código."

        else:
            if not facultad.codigo:
                facultad.codigo = codigo_unico(Facultad, facultad.nombre, facultad.pk)

            facultad.save()
            return redirect("facultad_list")

    return render(
        request,
        "academico/facultad_form.html",
        {
            "facultad": facultad,
            "error": error,
            **_contexto_codigo(Facultad, facultad),
        },
    )


@coordinador_required
def facultad_create(request):
    return _guardar_facultad(request, Facultad(activo=True))


@coordinador_required
def facultad_update(request, pk):
    return _guardar_facultad(request, get_object_or_404(Facultad, pk=pk))


@coordinador_required
def facultad_delete(request, pk):
    facultad = get_object_or_404(Facultad, pk=pk)

    if request.method == "POST":
        return _eliminar(request, facultad, "facultad_list")

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


def _guardar_carrera(request, carrera):
    es_nuevo = carrera.pk is None

    # En edición mostramos todas para conservar correctamente
    # una relación existente aunque la facultad esté inactiva.
    facultades = Facultad.objects.all().order_by("nombre")
    if es_nuevo:
        facultades = facultades.filter(activo=True)

    error = None

    if request.method == "POST":
        carrera.codigo = normalizar_codigo(request.POST.get("codigo")) or None
        carrera.nombre = request.POST.get("nombre", "").strip()
        carrera.activo = request.POST.get("activo") == "on"
        facultad_id = request.POST.get("facultad")

        if facultad_id:
            carrera.facultad = get_object_or_404(facultades, pk=facultad_id)

        if not carrera.nombre:
            error = "El nombre de la carrera es obligatorio."

        elif not facultad_id:
            error = "Debes seleccionar una facultad."

        elif nombre_repetido(
            Carrera.objects.filter(facultad=carrera.facultad),
            carrera.nombre,
            carrera.pk,
        ):
            error = "Ya existe una carrera con ese nombre en esta facultad."

        elif (
            carrera.codigo
            and Carrera.objects
            .filter(codigo__iexact=carrera.codigo)
            .exclude(pk=carrera.pk)
            .exists()
        ):
            error = "Ya existe una carrera con ese código."

        else:
            if not carrera.codigo:
                carrera.codigo = codigo_unico(Carrera, carrera.nombre, carrera.pk)

            carrera.save()
            return redirect("carrera_list")

    return render(
        request,
        "academico/carrera_form.html",
        {
            "carrera": carrera,
            "facultades": facultades,
            "error": error,
            **_contexto_codigo(Carrera, carrera),
        },
    )


@coordinador_required
def carrera_create(request):
    return _guardar_carrera(request, Carrera(activo=True))


@coordinador_required
def carrera_update(request, pk):
    return _guardar_carrera(request, get_object_or_404(Carrera, pk=pk))


@coordinador_required
def carrera_delete(request, pk):
    carrera = get_object_or_404(
        Carrera.objects.select_related("facultad"),
        pk=pk,
    )

    if request.method == "POST":
        return _eliminar(request, carrera, "carrera_list")

    return render(
        request,
        "academico/carrera_confirm_delete.html",
        {
            "carrera": carrera,
        },
    )

# =========================================================
# CRUD UNIDADES ACADÉMICAS
# =========================================================

@coordinador_required
def unidad_academica_list(request):
    unidades = (
        UnidadAcademica.objects
        .select_related("facultad", "carrera")
        .all()
        .order_by("nombre")
    )

    return render(
        request,
        "academico/unidad_academica_list.html",
        {
            "unidades": unidades,
        },
    )


def _guardar_unidad_academica(request, unidad):
    es_nuevo = unidad.pk is None

    facultades = Facultad.objects.all().order_by("nombre")
    carreras = Carrera.objects.all().order_by("nombre")
    if es_nuevo:
        facultades = facultades.filter(activo=True)
        carreras = carreras.filter(activo=True)

    error = None

    if request.method == "POST":
        facultad_id = request.POST.get("facultad")
        carrera_id = request.POST.get("carrera")

        tipo_guardado = unidad.tipo
        unidad.tipo = request.POST.get("tipo", "").strip()
        unidad.nombre = request.POST.get("nombre", "").strip()
        unidad.correo_oficial = request.POST.get("correo_oficial", "").strip() or None
        unidad.activo = request.POST.get("activo") == "on"
        unidad.facultad = (
            get_object_or_404(facultades, pk=facultad_id)
            if facultad_id else None
        )
        unidad.carrera = (
            get_object_or_404(carreras, pk=carrera_id)
            if carrera_id else None
        )

        # Si solo se eligió la carrera, la facultad se deduce de ella.
        if unidad.carrera and not unidad.facultad:
            unidad.facultad = unidad.carrera.facultad

        if not constantes.opcion_valida(unidad.tipo, constantes.TIPOS_UNIDAD_ACADEMICA, tipo_guardado):
            error = "Debes seleccionar el tipo de unidad académica."

        elif not unidad.nombre:
            error = "El nombre de la unidad académica es obligatorio."

        elif nombre_repetido(UnidadAcademica.objects, unidad.nombre, unidad.pk):
            error = "Ya existe una unidad académica con ese nombre."

        elif not unidad.facultad:
            error = "Debes seleccionar la facultad de la unidad académica."

        elif unidad.carrera and unidad.carrera.facultad_id != unidad.facultad.pk:
            error = "La carrera seleccionada no pertenece a la facultad elegida."

        elif unidad.tipo == "Dirección de Carrera" and not unidad.carrera:
            error = "Una Dirección de Carrera debe tener una carrera asociada."

        else:
            if unidad.correo_oficial:
                try:
                    validate_email(unidad.correo_oficial)
                except ValidationError:
                    error = "Ingresa un correo electrónico válido."

            if not error:
                unidad.save()
                return redirect("unidad_academica_list")

    return render(
        request,
        "academico/unidad_academica_form.html",
        {
            "unidad": unidad,
            "tipos": constantes.opciones_con_actual(constantes.TIPOS_UNIDAD_ACADEMICA, unidad.tipo),
            "facultades": facultades,
            "carreras": carreras,
            "error": error,
        },
    )


@coordinador_required
def unidad_academica_create(request):
    return _guardar_unidad_academica(request, UnidadAcademica(activo=True))


@coordinador_required
def unidad_academica_update(request, pk):
    unidad = get_object_or_404(
        UnidadAcademica.objects.select_related(
            "facultad",
            "carrera",
        ),
        pk=pk,
    )

    return _guardar_unidad_academica(request, unidad)


@coordinador_required
def unidad_academica_delete(request, pk):
    unidad = get_object_or_404(
        UnidadAcademica.objects.select_related(
            "facultad",
            "carrera",
        ),
        pk=pk,
    )

    if request.method == "POST":
        return _eliminar(request, unidad, "unidad_academica_list")

    return render(
        request,
        "academico/unidad_academica_confirm_delete.html",
        {
            "unidad": unidad,
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


def _guardar_asignatura(request, asignatura):
    es_nuevo = asignatura.pk is None

    # En edición mostramos todas para conservar
    # correctamente asociaciones existentes.
    carreras = Carrera.objects.all().order_by("nombre")
    if es_nuevo:
        carreras = carreras.filter(activo=True)

    error = None

    carreras_seleccionadas = (
        [] if es_nuevo
        else list(asignatura.carreras.values_list("id", flat=True))
    )

    if request.method == "POST":
        asignatura.codigo = normalizar_codigo(request.POST.get("codigo")) or None
        asignatura.nombre = request.POST.get("nombre", "").strip()
        asignatura.activo = request.POST.get("activo") == "on"

        # Relación N:M. Conservamos la selección si ocurre un error.
        carrera_ids = request.POST.getlist("carreras")
        carreras_seleccionadas = _ids_seleccionados(carrera_ids)

        carreras_objetos = carreras.filter(pk__in=carreras_seleccionadas)

        if not asignatura.nombre:
            error = "El nombre de la asignatura es obligatorio."

        elif not carrera_ids:
            error = "Debes seleccionar al menos una carrera."

        elif nombre_repetido(Asignatura.objects, asignatura.nombre, asignatura.pk):
            error = (
                "Ya existe una asignatura con ese nombre. "
                "Agrega la carrera a esa asignatura en vez de crear otra."
            )

        elif (
            asignatura.codigo
            and Asignatura.objects
            .filter(codigo__iexact=asignatura.codigo)
            .exclude(pk=asignatura.pk)
            .exists()
        ):
            error = "Ya existe una asignatura con ese código."

        elif carreras_objetos.count() != len(set(carrera_ids)):
            error = "Una de las carreras seleccionadas no existe o está inactiva."

        else:
            with transaction.atomic():
                asignatura.save()

                # Reemplazamos las asociaciones anteriores por las nuevas.
                AsignaturaCarrera.objects.filter(
                    asignatura=asignatura
                ).delete()

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
def asignatura_create(request):
    return _guardar_asignatura(request, Asignatura(activo=True))


@coordinador_required
def asignatura_update(request, pk):
    asignatura = get_object_or_404(
        Asignatura.objects.prefetch_related("carreras"),
        pk=pk,
    )

    return _guardar_asignatura(request, asignatura)


@coordinador_required
def asignatura_delete(request, pk):
    asignatura = get_object_or_404(
        Asignatura.objects.prefetch_related("carreras"),
        pk=pk,
    )

    if request.method == "POST":
        return _eliminar(request, asignatura, "asignatura_list")

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


def _guardar_docente(request, docente):
    error = None

    if request.method == "POST":
        docente.rut = request.POST.get("rut", "").strip()
        docente.nombres = request.POST.get("nombres", "").strip()
        docente.apellidos = request.POST.get("apellidos", "").strip()
        docente.correo_institucional = request.POST.get(
            "correo_institucional",
            ""
        ).strip()
        docente.telefono = request.POST.get("telefono", "").strip() or None
        docente.activo = request.POST.get("activo") == "on"

        # VALIDACIONES
        # El RUT se guarda sin puntos y con guion, igual que en el resto
        # del portal, para que la planificación encuentre al docente.
        try:
            docente.rut = validar_rut_chileno(docente.rut)
            error_rut = None
        except ValidationError as error_validacion:
            error_rut = error_validacion.message

        if error_rut:
            error = error_rut

        elif not docente.nombres:
            error = "Los nombres del docente son obligatorios."

        elif not docente.apellidos:
            error = "Los apellidos del docente son obligatorios."

        elif not docente.correo_institucional:
            error = "El correo institucional es obligatorio."

        elif (
            Docente.objects
            .filter(rut__iexact=docente.rut)
            .exclude(pk=docente.pk)
            .exists()
        ):
            error = "Ya existe un docente con ese RUT."

        elif (
            Docente.objects
            .filter(correo_institucional__iexact=docente.correo_institucional)
            .exclude(pk=docente.pk)
            .exists()
        ):
            error = "Ya existe un docente con ese correo institucional."

        else:
            try:
                validate_email(docente.correo_institucional)
            except ValidationError:
                error = "Ingresa un correo electrónico válido."
            else:
                docente.save()
                return redirect("docente_list")

    return render(
        request,
        "academico/docente_form.html",
        {
            "docente": docente,
            "error": error,
        },
    )


@coordinador_required
def docente_create(request):
    return _guardar_docente(request, Docente(activo=True))


@coordinador_required
def docente_update(request, pk):
    return _guardar_docente(request, get_object_or_404(Docente, pk=pk))


@coordinador_required
def docente_delete(request, pk):
    docente = get_object_or_404(
        Docente,
        pk=pk,
    )

    if request.method == "POST":
        return _eliminar(request, docente, "docente_list")

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


def _guardar_periodo(request, periodo):
    error = None

    if request.method == "POST":
        anio = request.POST.get("anio", "").strip()
        fecha_inicio = request.POST.get("fecha_inicio", "").strip()
        fecha_fin = request.POST.get("fecha_fin", "").strip()

        periodo.anio = anio
        tipo_guardado, estado_guardado = periodo.tipo, periodo.estado
        periodo.tipo = request.POST.get("tipo", "").strip()
        periodo.nombre = request.POST.get("nombre", "").strip()
        parte = request.POST.get("parte", "").strip()
        periodo.fecha_inicio = fecha_inicio or None
        periodo.fecha_fin = fecha_fin or None
        periodo.estado = request.POST.get("estado", "").strip()

        # Sin JS el nombre puede llegar vacío: se arma con la parte del año
        # (semestre, trimestre...) y el año.
        if not periodo.nombre:
            periodo.nombre = constantes.nombre_periodo(periodo.tipo, parte, anio)

        if not anio:
            error = "El año es obligatorio."

        elif not anio.isdigit():
            error = "El año debe ser un número válido."

        elif len(anio) != 4:
            error = "El año debe contener 4 dígitos."

        elif int(anio) < 2000 or int(anio) > 2100:
            error = "El año debe estar entre 2000 y 2100."

        elif not constantes.opcion_valida(periodo.tipo, constantes.TIPOS_PERIODO, tipo_guardado):
            error = "Debes seleccionar un tipo de período válido."

        elif not periodo.nombre:
            error = "El nombre del período es obligatorio."

        elif not constantes.opcion_valida(periodo.estado, constantes.ESTADOS_PERIODO, estado_guardado):
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
                tipo=periodo.tipo,
                nombre__iexact=periodo.nombre,
            )
            .exclude(pk=periodo.pk)
            .exists()
        ):
            error = (
                "Ya existe un período académico con "
                "ese año, tipo y nombre."
            )

        else:
            periodo.anio = int(anio)
            periodo.save()
            return redirect("periodo_list")

    return render(
        request,
        "academico/periodo_form.html",
        {
            "periodo": periodo,
            "tipos": constantes.opciones_con_actual(constantes.TIPOS_PERIODO, periodo.tipo),
            "estados": constantes.opciones_con_actual(constantes.ESTADOS_PERIODO, periodo.estado),
            "partes_periodo": constantes.PARTES_PERIODO,
            "error": error,
        },
    )


@coordinador_required
def periodo_create(request):
    return _guardar_periodo(request, PeriodoAcademico())


@coordinador_required
def periodo_update(request, pk):
    return _guardar_periodo(request, get_object_or_404(PeriodoAcademico, pk=pk))


@coordinador_required
def periodo_delete(request, pk):
    periodo = get_object_or_404(
        PeriodoAcademico,
        pk=pk,
    )

    if request.method == "POST":
        return _eliminar(request, periodo, "periodo_list")

    return render(
        request,
        "academico/periodo_confirm_delete.html",
        {
            "periodo": periodo,
        },
    )

# =========================================================
# SECCIONES / NRC
# =========================================================
#
# Un solo listado con filtros (período, carrera, asignatura, docente,
# NRC, sede y campus; RNF-ALC-01) y las acciones de editar y eliminar.
# El detalle de la sección es core:detalle_seccion, común a Coordinador
# y Docente.

FILTROS_SECCION = [
    "periodo",
    "sede",
    "campus",
    "carrera",
    "asignatura",
    "docente",
]


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
    )

    # -------------------------
    # FILTROS
    # -------------------------

    filtros = {
        nombre: request.GET.get(nombre, "").strip()
        for nombre in FILTROS_SECCION + ["nrc"]
    }

    campos_filtro = {
        "periodo": "periodo_id",
        "sede": "campus__sede_id",
        "campus": "campus_id",
        "carrera": "carreras__id",
        "asignatura": "asignatura_id",
        "docente": "docentes__id",
    }

    for nombre, campo in campos_filtro.items():
        valor = filtros[nombre]

        if valor.isdigit():
            secciones = secciones.filter(**{campo: int(valor)})
        elif valor:
            secciones = secciones.none()

    if filtros["nrc"]:
        secciones = secciones.filter(
            nrc__icontains=filtros["nrc"]
        )

    # Las relaciones N:M pueden generar filas repetidas.
    secciones = (
        secciones
        .distinct()
        .order_by(
            "-periodo__anio",
            "periodo__nombre",
            "asignatura__nombre",
            "nrc",
        )
    )

    # -------------------------
    # OPCIONES DE LOS FILTROS
    # -------------------------

    context = {
        "secciones": secciones,
        "periodos": PeriodoAcademico.objects.order_by("-anio", "nombre"),
        "sedes": Sede.objects.order_by("nombre"),
        "campus_list": (
            Campus.objects
            .select_related("sede")
            .order_by("sede__nombre", "nombre")
        ),
        "carreras": Carrera.objects.order_by("nombre"),
        "asignaturas": Asignatura.objects.order_by("nombre"),
        "docentes": Docente.objects.order_by("apellidos", "nombres"),
        "filtros": filtros,
        "filtros_activos": any(filtros.values()),
    }

    return render(
        request,
        "academico/seccion_list.html",
        context,
    )


def _sincronizar_relacion(modelo, seccion, campo, seleccionados):
    """
    Deja en la sección solo los registros seleccionados sin recrear los que
    se mantienen: así no se pierden los datos que cargó la planificación
    (nivel, declaración A+S, estudiantes, tipo de contrato, capacitado A+S).
    """
    actuales = modelo.objects.filter(seccion=seccion)
    ids_seleccionados = {objeto.pk for objeto in seleccionados}
    ids_actuales = set(actuales.values_list(f"{campo}_id", flat=True))

    actuales.exclude(**{f"{campo}_id__in": ids_seleccionados}).delete()

    modelo.objects.bulk_create([
        modelo(seccion=seccion, **{campo: objeto})
        for objeto in seleccionados
        if objeto.pk not in ids_actuales
    ])


def _guardar_seccion(request, seccion):
    es_nuevo = seccion.pk is None

    # Al crear solo se ofrecen registros activos. En edición mostramos
    # todos para no perder relaciones antiguas si alguno quedó inactivo.
    asignaturas = Asignatura.objects.all().order_by("nombre")
    docentes = Docente.objects.all().order_by("apellidos", "nombres")
    campus_list = (
        Campus.objects
        .select_related("sede")
        .order_by("sede__nombre", "nombre")
    )
    carreras = Carrera.objects.all().order_by("nombre")

    if es_nuevo:
        asignaturas = asignaturas.filter(activo=True)
        docentes = docentes.filter(activo=True)
        campus_list = campus_list.filter(activo=True)
        carreras = carreras.filter(activo=True)

    periodos = PeriodoAcademico.objects.all().order_by("-anio", "nombre")

    error = None

    if es_nuevo:
        carreras_seleccionadas = []
        docentes_seleccionados = []
    else:
        carreras_seleccionadas = list(
            seccion.carreras.values_list("id", flat=True)
        )
        docentes_seleccionados = list(
            seccion.docentes.values_list("id", flat=True)
        )

    if request.method == "POST":

        seccion.nrc = normalizar_codigo(request.POST.get("nrc"))
        seccion.seccion = request.POST.get("seccion", "").strip()
        jornada_guardada = seccion.jornada
        seccion.jornada = request.POST.get("jornada", "").strip() or None
        seccion.horario = request.POST.get("horario", "").strip() or None
        estado_guardado = seccion.estado
        seccion.estado = request.POST.get("estado", "").strip()

        asignatura_id = request.POST.get("asignatura")
        periodo_id = request.POST.get("periodo")
        campus_id = request.POST.get("campus")

        if asignatura_id:
            seccion.asignatura = get_object_or_404(asignaturas, pk=asignatura_id)
        if periodo_id:
            seccion.periodo = get_object_or_404(periodos, pk=periodo_id)
        if campus_id:
            seccion.campus = get_object_or_404(campus_list, pk=campus_id)

        docente_ids = request.POST.getlist("docentes")
        carrera_ids = request.POST.getlist("carreras")

        # Mantiene las selecciones si ocurre un error.
        docentes_seleccionados = _ids_seleccionados(docente_ids)
        carreras_seleccionadas = _ids_seleccionados(carrera_ids)

        docentes_objetos = docentes.filter(pk__in=docentes_seleccionados)
        carreras_objetos = carreras.filter(pk__in=carreras_seleccionadas)

        if not seccion.nrc:
            error = "El NRC es obligatorio."

        elif not seccion.seccion:
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

        elif not constantes.opcion_valida(seccion.estado, constantes.ESTADOS_SECCION, estado_guardado):
            error = "Debes seleccionar el estado de la sección."

        elif seccion.jornada and not constantes.opcion_valida(
            seccion.jornada, constantes.JORNADAS, jornada_guardada
        ):
            error = "Debes seleccionar una jornada de la lista."

        elif (
            Seccion.objects
            .filter(
                periodo_id=periodo_id,
                nrc__iexact=seccion.nrc,
            )
            .exclude(pk=seccion.pk)
            .exists()
        ):
            error = (
                "Ya existe una sección con este NRC "
                "en el período seleccionado."
            )

        elif docentes_objetos.count() != len(set(docente_ids)):
            error = (
                "Uno de los docentes seleccionados "
                "no existe o está inactivo."
            )

        elif carreras_objetos.count() != len(set(carrera_ids)):
            error = (
                "Una de las carreras seleccionadas "
                "no existe o está inactiva."
            )

        else:

            with transaction.atomic():

                seccion.save()
                _sincronizar_relacion(SeccionDocente, seccion, "docente", docentes_objetos)
                _sincronizar_relacion(SeccionCarrera, seccion, "carrera", carreras_objetos)

            return redirect("seccion_list")

    return render(
        request,
        "academico/seccion_form.html",
        {
            "seccion": seccion,
            "estados": constantes.opciones_con_actual(constantes.ESTADOS_SECCION, seccion.estado),
            "jornadas": constantes.opciones_con_actual(constantes.JORNADAS, seccion.jornada),
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
def seccion_create(request):
    return _guardar_seccion(request, Seccion())


@coordinador_required
def seccion_update(request, pk):
    seccion = get_object_or_404(
        Seccion.objects.prefetch_related(
            "carreras",
            "docentes",
        ),
        pk=pk,
    )

    return _guardar_seccion(request, seccion)


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
        return _eliminar(request, seccion, "seccion_list")

    return render(
        request,
        "academico/seccion_confirm_delete.html",
        {
            "seccion": seccion,
        },
    )
