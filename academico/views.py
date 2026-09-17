from django.shortcuts import render, redirect, get_object_or_404
from .models import (
    Campus,
    Sede,
    Facultad,
    Carrera,
    Asignatura,
    Seccion,
    Docente,
    Periodo
)
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


#crud campus
def campus_list(request):
    campus = Campus.objects.all()
    return render(request, 'academico/campus_list.html', {'campus': campus})


def campus_create(request):
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        direccion = request.POST.get('direccion', '').strip()

        if not nombre or not direccion:
            error = 'Todos los campos son obligatorios.'
        else:
            Campus.objects.create(
                nombre=nombre,
                direccion=direccion
            )
            return redirect('campus_list')

    return render(
        request,
        'academico/campus_form.html',
        {
            'error': error
        }
    )

def campus_update(request, pk):
    campus = get_object_or_404(Campus, pk=pk)
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        direccion = request.POST.get('direccion', '').strip()

        if not nombre or not direccion:
            error = 'Todos los campos son obligatorios.'
        else:
            campus.nombre = nombre
            campus.direccion = direccion
            campus.save()

            return redirect('campus_list')

    return render(
        request,
        'academico/campus_form.html',
        {
            'campus': campus,
            'error': error
        }
    )


def campus_delete(request, pk):
    campus = get_object_or_404(Campus, pk=pk)
    campus.delete()
    return redirect('campus_list')

def home(request):
    return render(request, 'academico/home.html')

#-----------------------------------------------------------------------------------
#crud sede

# LISTAR
def sede_list(request):
    sedes = Sede.objects.select_related('campus').all()
    return render(request, 'academico/sede_list.html', {'sedes': sedes})


# CREAR
def sede_create(request):
    campus = Campus.objects.all()
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        ciudad = request.POST.get('ciudad', '').strip()
        campus_id = request.POST.get('campus')

        if not nombre or not ciudad or not campus_id:
            error = 'Todos los campos son obligatorios.'
        else:
            campus_obj = get_object_or_404(Campus, pk=campus_id)

            Sede.objects.create(
                nombre=nombre,
                ciudad=ciudad,
                campus=campus_obj
            )

            return redirect('sede_list')

    return render(
        request,
        'academico/sede_form.html',
        {
            'campus': campus,
            'error': error
        }
    )


# EDITAR
def sede_update(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    campus = Campus.objects.all()
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        ciudad = request.POST.get('ciudad', '').strip()
        campus_id = request.POST.get('campus')

        # VALIDACIÓN
        if not nombre or not ciudad or not campus_id:
            error = 'Todos los campos son obligatorios.'

        else:
            campus_obj = get_object_or_404(Campus, pk=campus_id)

            sede.nombre = nombre
            sede.ciudad = ciudad
            sede.campus = campus_obj
            sede.save()

            return redirect('sede_list')

    return render(
        request,
        'academico/sede_form.html',
        {
            'sede': sede,
            'campus': campus,
            'error': error
        }
    )


# ELIMINAR
def sede_delete(request, pk):
    sede = get_object_or_404(Sede, pk=pk)
    if request.method == 'POST':
        sede.delete()
        return redirect('sede_list')

    return render(request, 'academico/sede_delete.html', {'sede': sede})
#----------------------------------------------------------------------------------
#CRUD FACULTADES

def facultad_list(request):
    facultades = Facultad.objects.all()
    return render(
        request,
        'academico/facultad_list.html',
        {'facultades': facultades}
    )


def facultad_create(request):
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        if not nombre:
            error = 'El nombre de la facultad es obligatorio.'
        else:
            Facultad.objects.create(nombre=nombre)
            return redirect('facultad_list')

    return render(
        request,
        'academico/facultad_form.html',
        {'error': error}
    )

def facultad_update(request, pk):
    facultad = get_object_or_404(Facultad, pk=pk)
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()

        # VALIDACIÓN
        if not nombre:
            error = 'El nombre de la facultad es obligatorio.'

        else:
            facultad.nombre = nombre
            facultad.save()

            return redirect('facultad_list')

    return render(
        request,
        'academico/facultad_form.html',
        {
            'facultad': facultad,
            'error': error
        }
    )

def facultad_delete(request, pk):
    facultad = get_object_or_404(Facultad, pk=pk)

    if request.method == 'POST':
        facultad.delete()
        return redirect('facultad_list')

    return render(
        request,
        'academico/facultad_confirm_delete.html',
        {'facultad': facultad}
    )

#------------------------------------------------------------------------------------
# CRUD CARRERAS

def carrera_list(request):
    carreras = Carrera.objects.select_related('facultad').all()

    return render(
        request,
        'academico/carrera_list.html',
        {'carreras': carreras}
    )


def carrera_create(request):
    facultades = Facultad.objects.all()
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        facultad_id = request.POST.get('facultad')

        # VALIDACIONES
        if not nombre:
            error = 'El nombre de la carrera es obligatorio.'

        elif not facultad_id:
            error = 'Debes seleccionar una facultad.'

        else:
            facultad = get_object_or_404(
                Facultad,
                pk=facultad_id
            )

            Carrera.objects.create(
                nombre=nombre,
                facultad=facultad
            )

            return redirect('carrera_list')

    return render(
        request,
        'academico/carrera_form.html',
        {
            'facultades': facultades,
            'error': error
        }
    )

def carrera_update(request, pk):
    carrera = get_object_or_404(Carrera, pk=pk)
    facultades = Facultad.objects.all()
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        facultad_id = request.POST.get('facultad')

        # VALIDACIONES
        if not nombre:
            error = 'El nombre de la carrera es obligatorio.'

        elif not facultad_id:
            error = 'Debes seleccionar una facultad.'

        else:
            facultad = get_object_or_404(
                Facultad,
                pk=facultad_id
            )

            carrera.nombre = nombre
            carrera.facultad = facultad
            carrera.save()

            return redirect('carrera_list')

    return render(
        request,
        'academico/carrera_form.html',
        {
            'carrera': carrera,
            'facultades': facultades,
            'error': error
        }
    )


def carrera_delete(request, pk):
    carrera = get_object_or_404(Carrera, pk=pk)

    if request.method == 'POST':
        carrera.delete()
        return redirect('carrera_list')

    return render(
        request,
        'academico/carrera_confirm_delete.html',
        {'carrera': carrera}
    )
#-----------------------------------------------------------
# CRUD ASIGNATURAS



def asignatura_list(request):
    asignaturas = Asignatura.objects.select_related('carrera').all()

    return render(
        request,
        'academico/asignatura_list.html',
        {'asignaturas': asignaturas}
    )


def asignatura_create(request):
    carreras = Carrera.objects.all()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        carrera_id = request.POST.get('carrera')

        if nombre and carrera_id:
            carrera = get_object_or_404(Carrera, pk=carrera_id)

            Asignatura.objects.create(
                nombre=nombre,
                carrera=carrera
            )

            return redirect('asignatura_list')

    return render(
        request,
        'academico/asignatura_form.html',
        {'carreras': carreras}
    )


def asignatura_update(request, pk):
    asignatura = get_object_or_404(Asignatura, pk=pk)
    carreras = Carrera.objects.all()

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        carrera_id = request.POST.get('carrera')

        if nombre and carrera_id:
            carrera = get_object_or_404(Carrera, pk=carrera_id)

            asignatura.nombre = nombre
            asignatura.carrera = carrera
            asignatura.save()

            return redirect('asignatura_list')

    return render(
        request,
        'academico/asignatura_form.html',
        {
            'asignatura': asignatura,
            'carreras': carreras
        }
    )


def asignatura_delete(request, pk):
    asignatura = get_object_or_404(Asignatura, pk=pk)

    if request.method == 'POST':
        asignatura.delete()
        return redirect('asignatura_list')

    return render(
        request,
        'academico/asignatura_confirm_delete.html',
        {'asignatura': asignatura}
    )

# =========================
# CRUD SECCIONES / NRC
# =========================

def seccion_list(request):
    secciones = Seccion.objects.select_related(
        'asignatura',
        'docente',
        'periodo',
        'sede'
    ).all()

    return render(
        request,
        'academico/seccion_list.html',
        {'secciones': secciones}
    )


def seccion_create(request):
    asignaturas = Asignatura.objects.all()
    docentes = Docente.objects.all()
    periodos = Periodo.objects.all()
    sedes = Sede.objects.all()

    error = None

    if request.method == 'POST':
        nrc = request.POST.get('nrc', '').strip()
        asignatura_id = request.POST.get('asignatura')
        docente_id = request.POST.get('docente')
        periodo_id = request.POST.get('periodo')
        sede_id = request.POST.get('sede')

        if not nrc or not asignatura_id or not docente_id or not periodo_id or not sede_id:
            error = 'Todos los campos son obligatorios.'

        elif Seccion.objects.filter(nrc=nrc).exists():
            error = 'Ya existe una sección con este NRC.'

        else:
            asignatura = get_object_or_404(Asignatura, pk=asignatura_id)
            docente = get_object_or_404(Docente, pk=docente_id)
            periodo = get_object_or_404(Periodo, pk=periodo_id)
            sede = get_object_or_404(Sede, pk=sede_id)

            Seccion.objects.create(
                nrc=nrc,
                asignatura=asignatura,
                docente=docente,
                periodo=periodo,
                sede=sede
            )

            return redirect('seccion_list')

    return render(
        request,
        'academico/seccion_form.html',
        {
            'asignaturas': asignaturas,
            'docentes': docentes,
            'periodos': periodos,
            'sedes': sedes,
            'error': error
        }
    )


def seccion_update(request, pk):
    seccion = get_object_or_404(Seccion, pk=pk)

    asignaturas = Asignatura.objects.all()
    docentes = Docente.objects.all()
    periodos = Periodo.objects.all()
    sedes = Sede.objects.all()

    error = None

    if request.method == 'POST':
        nrc = request.POST.get('nrc', '').strip()
        asignatura_id = request.POST.get('asignatura')
        docente_id = request.POST.get('docente')
        periodo_id = request.POST.get('periodo')
        sede_id = request.POST.get('sede')

        if not nrc or not asignatura_id or not docente_id or not periodo_id or not sede_id:
            error = 'Todos los campos son obligatorios.'

        elif Seccion.objects.filter(nrc=nrc).exclude(pk=pk).exists():
            error = 'Ya existe otra sección con este NRC.'

        else:
            seccion.nrc = nrc
            seccion.asignatura = get_object_or_404(
                Asignatura,
                pk=asignatura_id
            )
            seccion.docente = get_object_or_404(
                Docente,
                pk=docente_id
            )
            seccion.periodo = get_object_or_404(
                Periodo,
                pk=periodo_id
            )
            seccion.sede = get_object_or_404(
                Sede,
                pk=sede_id
            )

            seccion.save()

            return redirect('seccion_list')

    return render(
        request,
        'academico/seccion_form.html',
        {
            'seccion': seccion,
            'asignaturas': asignaturas,
            'docentes': docentes,
            'periodos': periodos,
            'sedes': sedes,
            'error': error
        }
    )


def seccion_delete(request, pk):
    seccion = get_object_or_404(Seccion, pk=pk)

    if request.method == 'POST':
        seccion.delete()
        return redirect('seccion_list')

    return render(
        request,
        'academico/seccion_confirm_delete.html',
        {'seccion': seccion}
    )

# =========================
# CRUD DOCENTES
# =========================

def docente_list(request):
    docentes = Docente.objects.all()

    return render(
        request,
        'academico/docente_list.html',
        {'docentes': docentes}
    )


def docente_create(request):
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        correo = request.POST.get('correo', '').strip()

        # VALIDACIONES
        if not nombre:
            error = 'El nombre del docente es obligatorio.'

        elif not correo:
            error = 'El correo electrónico es obligatorio.'

        else:
            try:
                validate_email(correo)

                Docente.objects.create(
                    nombre=nombre,
                    correo=correo
                )

                return redirect('docente_list')

            except ValidationError:
                error = 'Ingresa un correo electrónico válido.'

    return render(
        request,
        'academico/docente_form.html',
        {
            'error': error
        }
    )

def docente_update(request, pk):
    docente = get_object_or_404(Docente, pk=pk)
    error = None

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        correo = request.POST.get('correo', '').strip()

        if not nombre or not correo:
            error = 'Todos los campos son obligatorios.'
        else:
            docente.nombre = nombre
            docente.correo = correo
            docente.save()

            return redirect('docente_list')

    return render(
        request,
        'academico/docente_form.html',
        {
            'docente': docente,
            'error': error
        }
    )


def docente_delete(request, pk):
    docente = get_object_or_404(Docente, pk=pk)

    if request.method == 'POST':
        docente.delete()
        return redirect('docente_list')

    return render(
        request,
        'academico/docente_confirm_delete.html',
        {'docente': docente}
    )

# =========================
# CRUD PERIODOS
# =========================

def periodo_list(request):
    periodos = Periodo.objects.all().order_by('-anio', 'tipo')

    return render(
        request,
        'academico/periodo_list.html',
        {'periodos': periodos}
    )


def periodo_create(request):
    error = None

    if request.method == 'POST':
        anio = request.POST.get('anio', '').strip()
        tipo = request.POST.get('tipo', '').strip()

        # VALIDACIONES
        if not anio:
            error = 'El año es obligatorio.'

        elif not anio.isdigit():
            error = 'El año debe ser un número válido.'

        elif len(anio) != 4:
            error = 'El año debe contener 4 dígitos.'

        elif int(anio) < 2000 or int(anio) > 2100:
            error = 'El año debe estar entre 2000 y 2100.'

        elif not tipo:
            error = 'Debes seleccionar un tipo de período.'

        else:
            Periodo.objects.create(
                anio=int(anio),
                tipo=tipo
            )

            return redirect('periodo_list')

    return render(
        request,
        'academico/periodo_form.html',
        {
            'error': error
        }
    )

def periodo_update(request, pk):
    periodo = get_object_or_404(Periodo, pk=pk)
    error = None

    if request.method == 'POST':
        anio = request.POST.get('anio', '').strip()
        tipo = request.POST.get('tipo', '').strip()

        if not anio or not tipo:
            error = 'Todos los campos son obligatorios.'

        elif not anio.isdigit():
            error = 'El año debe ser un número válido.'

        else:
            periodo.anio = int(anio)
            periodo.tipo = tipo
            periodo.save()

            return redirect('periodo_list')

    return render(
        request,
        'academico/periodo_form.html',
        {
            'periodo': periodo,
            'error': error
        }
    )


def periodo_delete(request, pk):
    periodo = get_object_or_404(Periodo, pk=pk)

    if request.method == 'POST':
        periodo.delete()
        return redirect('periodo_list')

    return render(
        request,
        'academico/periodo_confirm_delete.html',
        {'periodo': periodo}
    )