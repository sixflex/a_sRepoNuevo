from datetime import datetime, time, timedelta
import base64
from io import BytesIO
from urllib import request
import re
import qrcode
import uuid
from django.db import transaction, IntegrityError
from django.db.models import Max
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from socios.models import SocioComunitario

from usuarios.decorators import coordinador_required, docente_required

from planificacion.models import PlanificacionEnlace
from planificacion.email_service import enviar_correo_planificacion
from academico.models import Seccion

from academico.models import (
    Campus,
    Docente,
    PeriodoAcademico,
    Seccion,
    UnidadAcademica,
)

from .models import (
    EnlaceRegistroEquipo,
    Equipo,
    IntegranteEquipo,
)

from auditoria.services import registrar_auditoria
from django.core.exceptions import PermissionDenied

from .models import EnlaceRegistroEquipo
@coordinador_required
def coordinador_contexto(request):
    return render(request, "proyectos/coordinador_contexto.html")


@coordinador_required
def gestionar_enlaces_planificacion(request):
    if request.method == "POST":
        accion = request.POST.get("accion", "crear")

        if accion == "toggle_estado":
            enlace = get_object_or_404(
                PlanificacionEnlace,
                pk=request.POST.get("enlace_id"),
            )
            estado_anterior = enlace.activo
            enlace.activo = not enlace.activo
            enlace.save(update_fields=["activo"])
            registrar_auditoria(
                request=request,
                entidad="PlanificacionEnlace",
                entidad_id=enlace.id,
                accion=(
                    "ACTIVAR_ENLACE"
                    if enlace.activo
                    else "DESACTIVAR_ENLACE"
                ),
                valores_anteriores={
                    "activo": estado_anterior,
                },
                valores_nuevos={
                    "activo": enlace.activo,
                },
            )

            messages.success(
                request,
                "El enlace fue activado."
                if enlace.activo
                else "El enlace fue desactivado.",
            )
            return redirect("proyectos:gestionar_enlaces")

        if accion == "reenviar":
            enlace = get_object_or_404(
            PlanificacionEnlace,
            pk=request.POST.get("enlace_id"),
            )

            ahora = timezone.now()

            if not enlace.activo:
                messages.error(
                    request,
                    "No se puede reenviar un enlace que está inactivo.",
                )
                return redirect("proyectos:gestionar_enlaces")

            if (
                enlace.fecha_expiracion is not None
                and enlace.fecha_expiracion < ahora
            ):
                messages.error(
                    request,
                    "No se puede reenviar un enlace que ya expiró.",
                )
                return redirect("proyectos:gestionar_enlaces")

            try:
                enviado = enviar_correo_planificacion(
                    request,
                    enlace,
                    reenvio=True,
                )

                if enviado:
                    registrar_auditoria(
                        request=request,
                        entidad="PlanificacionEnlace",
                        entidad_id=enlace.id,
                        accion="REENVIAR_ENLACE",
                        valores_nuevos={
                            "destinatario_correo": enlace.destinatario_correo,
                            "fecha_reenvio": timezone.now().isoformat(),
                        },
                    )
                    messages.success(
                        request,
                        (
                            "El enlace fue reenviado correctamente a "
                            f"{enlace.destinatario_correo}."
                        ),
                    )
                else:
                    messages.error(
                        request,
                        "No fue posible reenviar el enlace.",
                    )

            except Exception:
                messages.error(
                    request,
                    (
                        "No fue posible enviar el correo. "
                        "Revise la configuración del servicio de correo."
                    ),
                )
            return redirect("proyectos:gestionar_enlaces")

        unidad_id = request.POST.get("unidad_academica")
        destinatario_nombre = (request.POST.get("destinatario_nombre") or "").strip()
        destinatario_correo = (request.POST.get("destinatario_email") or "").strip()
        campus_id = request.POST.get("campus")
        periodo_id = request.POST.get("periodo")
        fecha_expiracion_texto = request.POST.get("fecha_expiracion")

        if not all(
            [
                unidad_id,
                destinatario_nombre,
                destinatario_correo,
                campus_id,
                periodo_id,
                fecha_expiracion_texto,
            ]
        ):
            messages.error(
                request,
                "Debe completar todos los campos obligatorios.",
            )
        else:
            try:
                validate_email(destinatario_correo)
            except ValidationError:
                messages.error(
                    request,
                    "El correo del destinatario no tiene un formato válido.",
                )
                return redirect("proyectos:gestionar_enlaces")

            fecha_expiracion = parse_date(fecha_expiracion_texto)

            if fecha_expiracion is None:
                messages.error(
                    request,
                    "La fecha de expiración no es válida.",
                )
                return redirect("proyectos:gestionar_enlaces")

            # La fecha elegida se considera vigente hasta el final de ese día.
            fecha_expiracion_dt = timezone.make_aware(
                datetime.combine(fecha_expiracion, time.max)
            )

            if fecha_expiracion_dt <= timezone.now():
                messages.error(
                    request,
                    "La fecha de expiración debe ser posterior al momento actual.",
                )
                return redirect("proyectos:gestionar_enlaces")

            unidad = get_object_or_404(
                UnidadAcademica,
                pk=unidad_id,
                activo=True,
            )
            campus = get_object_or_404(
                Campus.objects.select_related("sede"),
                pk=campus_id,
                activo=True,
            )
            periodo = get_object_or_404(
                PeriodoAcademico,
                pk=periodo_id,
            )

            enlace = PlanificacionEnlace.objects.create(
                unidad_academica=unidad,
                campus=campus,
                periodo=periodo,
                destinatario_nombre=destinatario_nombre,
                destinatario_correo=destinatario_correo,
                fecha_emision=timezone.now(),
                fecha_expiracion=fecha_expiracion_dt,
                activo=True,
            )
            registrar_auditoria(
                request=request,
                entidad="PlanificacionEnlace",
                entidad_id=enlace.id,
                accion="CREAR_ENLACE",
                valores_nuevos={
                    "unidad_academica_id": enlace.unidad_academica_id,
                    "campus_id": enlace.campus_id,
                    "periodo_id": enlace.periodo_id,
                    "destinatario_nombre": enlace.destinatario_nombre,
                    "destinatario_correo": enlace.destinatario_correo,
                    "fecha_expiracion": (
                        enlace.fecha_expiracion.isoformat()
                        if enlace.fecha_expiracion
                        else None
                    ),
                    "activo": enlace.activo,
                },
            )
            try:
                enviado = enviar_correo_planificacion(
                    request,
                    enlace,
                    reenvio=False,
                )

                if enviado:
                    messages.success(
                        request,
                        (
                            f"Enlace generado y enviado correctamente a "
                            f"{destinatario_correo}."
                        ),
                    )
                else:
                    messages.warning(
                        request,
                        (
                            "El enlace fue generado correctamente, "
                            "pero no pudo enviarse por correo."
                        ),
                    )

            except Exception:
                messages.warning(
                    request,
                    (
                        "El enlace fue generado correctamente, "
                        "pero no pudo enviarse por correo. "
                        "Puede copiarlo manualmente desde la lista."
                    ),
                )

            return redirect("proyectos:gestionar_enlaces")

    enlaces = list(
        PlanificacionEnlace.objects.select_related(
            "unidad_academica",
            "unidad_academica__facultad",
            "unidad_academica__carrera",
            "campus__sede",
            "periodo",
        ).order_by("-fecha_emision", "-id")
    )

    ahora = timezone.now()
    for enlace in enlaces:
        enlace.esta_vigente = (
            enlace.activo
            and (
                enlace.fecha_expiracion is None
                or enlace.fecha_expiracion >= ahora
            )
        )

    unidades = (
        UnidadAcademica.objects.filter(activo=True)
        .select_related("facultad", "carrera")
        .order_by("tipo", "nombre")
    )
    campus = (
        Campus.objects.filter(activo=True)
        .select_related("sede")
        .order_by("sede__nombre", "nombre")
    )
    periodos = PeriodoAcademico.objects.all().order_by(
        "-anio",
        "tipo",
        "nombre",
    )

    return render(
        request,
        "proyectos/gestionar_enlaces.html",
        {
            "enlaces": enlaces,
            "unidades": unidades,
            "campus": campus,
            "periodos": periodos,
            "hoy": timezone.localdate().isoformat(),
        },
    )

@docente_required
def gestionar_registro_equipos(request, seccion_id):
    docente = get_object_or_404(
        Docente,
        usuario=request.user,
        activo=True,
    )

    seccion = get_object_or_404(
        Seccion.objects.select_related(
            "asignatura",
            "periodo",
            "campus",
            "campus__sede",
        ),
        pk=seccion_id,
    )

    # Verificar que el docente pertenezca a la sección
    if not seccion.docentes.filter(pk=docente.pk).exists():
        raise PermissionDenied

    # Obtener el enlace más reciente de la sección
    enlace = (
        EnlaceRegistroEquipo.objects
        .filter(seccion=seccion)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    if request.method == "POST":
        accion = request.POST.get("accion")

        # HABILITAR FORMULARIO Y CREAR ENLACE
        if accion == "habilitar":

            if enlace and enlace.activo:
                messages.warning(
                    request,
                    "El formulario de registro ya se encuentra habilitado.",
                )

            else:
                ahora = timezone.now()

                enlace = EnlaceRegistroEquipo.objects.create(
                    seccion=seccion,
                    creado_por_docente=docente,
                    fecha_inicio=ahora,
                    fecha_expiracion=ahora + timedelta(days=7),
                    activo=True,
                )

                messages.success(
                    request,
                    "El formulario de registro fue habilitado correctamente.",
                )

        # CERRAR FORMULARIO
        elif accion == "cerrar":

            if enlace and enlace.activo:
                enlace.activo = False
                enlace.fecha_expiracion = timezone.now()

                enlace.save(
                    update_fields=[
                        "activo",
                        "fecha_expiracion",
                    ]
                )

                messages.success(
                    request,
                    "El formulario de registro fue cerrado correctamente.",
                )

            else:
                messages.warning(
                    request,
                    "No existe un formulario habilitado para esta sección.",
                )

                return redirect(
            "proyectos:gestionar_registro_equipos",
            seccion_id=seccion.pk,
        )

        
    url_registro = None
    qr_base64 = None

    if enlace and enlace.activo:
        url_registro = request.build_absolute_uri(
            reverse(
                "proyectos:acceso_registro_equipos",
                kwargs={"token": enlace.token},
            )
        )

        
        qr = qrcode.make(url_registro)

        
        buffer = BytesIO()
        qr.save(buffer, format="PNG")

        
        qr_base64 = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

    return render(
        request,
        "proyectos/gestionar_registro_equipos.html",
        {
            "seccion": seccion,
            "enlace": enlace,
            "url_registro": url_registro,
            "qr_base64": qr_base64,
        },
    )

def limpiar_rut(rut):
    return (
        rut.replace(".", "")
        .replace("-", "")
        .replace(" ", "")
        .upper()
    )


def formatear_rut(rut):
    rut_limpio = limpiar_rut(rut)

    if len(rut_limpio) < 2:
        return rut_limpio

    return f"{rut_limpio[:-1]}-{rut_limpio[-1]}"


def validar_rut_chileno(rut):
    rut = rut.strip().upper()

    
    

    patron = r"^(?:\d{1,2}\.\d{3}\.\d{3}|\d{7,8})-[0-9K]$"

    if not re.fullmatch(patron, rut):
        return False

    rut_limpio = limpiar_rut(rut)

    cuerpo = rut_limpio[:-1]
    dv_ingresado = rut_limpio[-1]

    if not cuerpo.isdigit():
        return False

    suma = 0
    multiplicador = 2

    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador

        multiplicador += 1

        if multiplicador > 7:
            multiplicador = 2

    resto = 11 - (suma % 11)

    if resto == 11:
        dv_calculado = "0"
    elif resto == 10:
        dv_calculado = "K"
    else:
        dv_calculado = str(resto)

    return dv_ingresado == dv_calculado

def acceso_registro_equipos(request, token):
    enlace = get_object_or_404(
        EnlaceRegistroEquipo.objects.select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
            "seccion__campus",
        ),
        token=token,
    )

    ahora = timezone.now()

    
    if not enlace.activo:
        return render(
            request,
            "proyectos/registro_equipos_no_disponible.html",
            {
                "motivo": "El formulario de registro se encuentra cerrado.",
            },
            status=403,
        )

    if (
        enlace.fecha_expiracion
        and enlace.fecha_expiracion <= ahora
    ):
        return render(
            request,
            "proyectos/registro_equipos_no_disponible.html",
            {
                "motivo": "El enlace de registro ha expirado.",
            },
            status=403,
        )

    
    if not request.user.is_authenticated:
        return redirect_to_login(
            request.get_full_path(),
            login_url=reverse("usuarios:login"),
        )

    es_estudiante = request.user.groups.filter(
        name="Estudiante"
    ).exists()

    if not es_estudiante:
        return render(
            request,
            "proyectos/registro_equipos_no_disponible.html",
            {
                "motivo": (
                    "Este formulario solo puede ser utilizado "
                    "por estudiantes autenticados."
                ),
            },
            status=403,
        )

    
    socios_disponibles = (
        SocioComunitario.objects
        .filter(
            activo=True,
            es_provisional=False,
            estado_revision__in=["APROBADO", "DISPONIBLE"],
        )
        .select_related("clasificacion", "comuna")
        .order_by("nombre_organizacion")
    )

    errores = []
    datos_formulario = {}
    integrantes_validados = []

    socio_seleccionado = None
    socio_provisional_nombre = ""

    
    clave_idempotencia = request.POST.get(
        "clave_idempotencia",
        "",
    ).strip()

    if not clave_idempotencia:
        clave_idempotencia = str(uuid.uuid4())

    
    if request.method == "POST":

        
        tipo_socio = request.POST.get(
            "tipo_socio",
            "",
        ).strip()

        socio_comunitario_id = request.POST.get(
            "socio_comunitario",
            "",
        ).strip()

        socio_provisional_nombre = normalizar_nombre(
            request.POST.get(
                "socio_provisional_nombre",
                ""
            )
        )

        datos_formulario["tipo_socio"] = tipo_socio
        datos_formulario["socio_comunitario"] = socio_comunitario_id
        datos_formulario[
            "socio_provisional_nombre"
        ] = socio_provisional_nombre

        if tipo_socio not in ["existente", "provisional"]:
            errores.append(
                "Debes seleccionar cómo registrarás "
                "el Socio Comunitario."
            )

        elif tipo_socio == "existente":
            if not socio_comunitario_id:
                errores.append(
                    "Debes seleccionar un Socio Comunitario disponible."
                )
            else:
                try:
                    socio_seleccionado = (
                        SocioComunitario.objects
                        .filter(
                            pk=socio_comunitario_id,
                            activo=True,
                            es_provisional=False,
                            estado_revision__in=[
                                "APROBADO",
                                "DISPONIBLE",
                            ],
                        )
                        .first()
                    )

                    if socio_seleccionado is None:
                        errores.append(
                            "El Socio Comunitario seleccionado "
                            "no se encuentra disponible."
                        )

                except (ValueError, TypeError):
                    errores.append(
                        "El Socio Comunitario seleccionado no es válido."
                    )

        elif tipo_socio == "provisional":
            if not socio_provisional_nombre:
                errores.append(
                    "Debes ingresar el nombre de la organización "
                    "del Socio Comunitario provisional."
                )

            elif len(socio_provisional_nombre) > 220:
                errores.append(
                    "El nombre de la organización no puede superar "
                    "los 220 caracteres."
                )

        
        cantidad_raw = request.POST.get(
            "cantidad_integrantes",
            "",
        ).strip()

        datos_formulario["cantidad_integrantes"] = cantidad_raw

        try:
            cantidad_integrantes = int(cantidad_raw)
        except (TypeError, ValueError):
            cantidad_integrantes = 0

        if cantidad_integrantes < 1 or cantidad_integrantes > 6:
            errores.append(
                "La cantidad de integrantes debe estar entre 1 y 6."
            )

        ruts_utilizados = set()
        correos_utilizados = set()

        
        if 1 <= cantidad_integrantes <= 6:

            for i in range(1, cantidad_integrantes + 1):

                rut = request.POST.get(
                    f"rut_{i}",
                    "",
                ).strip()

                correo = request.POST.get(
                    f"correo_{i}",
                    "",
                ).strip().lower()

                nombres_declarados = request.POST.get(
                    f"nombres_{i}",
                    "",
                )

                apellidos_declarados = request.POST.get(
                    f"apellidos_{i}",
                    "",
                )

                nombres = normalizar_nombre(
                    nombres_declarados
                )

                apellidos = normalizar_nombre(
                    apellidos_declarados
                )

                
                datos_formulario[f"rut_{i}"] = rut
                datos_formulario[f"correo_{i}"] = correo
                datos_formulario[f"nombres_{i}"] = nombres
                datos_formulario[f"apellidos_{i}"] = apellidos

                if not rut:
                    errores.append(
                        f"Integrante {i}: el RUT es obligatorio."
                    )

                if not correo:
                    errores.append(
                        f"Integrante {i}: el correo institucional "
                        "es obligatorio."
                    )

                if not nombres:
                    errores.append(
                        f"Integrante {i}: los nombres son obligatorios."
                    )

                if not apellidos:
                    errores.append(
                        f"Integrante {i}: los apellidos son obligatorios."
                    )

                
                rut_normalizado = ""

                if rut:
                    if not validar_rut_chileno(rut):
                        errores.append(
                            f"Integrante {i}: el RUT ingresado "
                            "no es válido."
                        )

                    rut_normalizado = formatear_rut(rut)

                    if rut_normalizado in ruts_utilizados:
                        errores.append(
                            f"Integrante {i}: el RUT está repetido "
                            "dentro del equipo."
                        )
                    else:
                        ruts_utilizados.add(rut_normalizado)

                
                if correo:
                    try:
                        validate_email(correo)

                    except ValidationError:
                        errores.append(
                            f"Integrante {i}: el correo ingresado "
                            "no es válido."
                        )

                    if correo in correos_utilizados:
                        errores.append(
                            f"Integrante {i}: el correo está repetido "
                            "dentro del equipo."
                        )
                    else:
                        correos_utilizados.add(correo)

                integrantes_validados.append(
                    {
                        "rut": rut_normalizado,
                        "nombres": nombres,
                        "apellidos": apellidos,
                        "correo": correo,
                        "es_informante": i == 1,
                    }
                )

        
        correo_informante = (
            request.user.correo_institucional
            or request.user.email
            or ""
        ).strip().lower()

        if 1 <= cantidad_integrantes <= 6:

            correo_integrante_1 = (
                request.POST.get("correo_1", "")
                .strip()
                .lower()
            )

            if (
                correo_informante
                and correo_integrante_1 != correo_informante
            ):
                errores.append(
                    "El correo del estudiante informante no coincide "
                    "con la cuenta autenticada."
                )

        
        try:
            clave_uuid = uuid.UUID(
                clave_idempotencia
            )

        except (ValueError, TypeError, AttributeError):
            clave_uuid = None

            errores.append(
                "La solicitud de registro no es válida. "
                "Recarga el formulario e inténtalo nuevamente."
            )

        
        if clave_uuid:

            equipo_misma_solicitud = (
                Equipo.objects
                .filter(
                    clave_idempotencia=clave_uuid
                )
                .first()
            )

            if equipo_misma_solicitud:

                messages.info(
                    request,
                    (
                        "Este equipo ya fue registrado como "
                        f"Grupo {equipo_misma_solicitud.numero_grupo}."
                    ),
                )

                return redirect(
                    "proyectos:acceso_registro_equipos",
                    token=enlace.token,
                )

        
        if correo_informante:

            equipo_ya_registrado = (
                Equipo.objects
                .filter(
                    seccion=enlace.seccion,
                    informante_correo__iexact=correo_informante,
                )
                .first()
            )

            if equipo_ya_registrado:

                errores.append(
                    "Ya registraste un equipo en esta sección. "
                    f"Tu equipo corresponde al Grupo "
                    f"{equipo_ya_registrado.numero_grupo}."
                )

        
        if not errores:

            try:
                with transaction.atomic():

                    
                    seccion_bloqueada = (
                        Seccion.objects
                        .select_for_update()
                        .get(pk=enlace.seccion_id)
                    )

                    
                    equipo_existente = (
                        Equipo.objects
                        .filter(
                            clave_idempotencia=clave_uuid
                        )
                        .first()
                    )

                    if equipo_existente:

                        numero_grupo = (
                            equipo_existente.numero_grupo
                        )

                    else:

                        
                        equipo_informante_existente = (
                            Equipo.objects
                            .filter(
                                seccion=seccion_bloqueada,
                                informante_correo__iexact=correo_informante,
                            )
                            .first()
                        )

                        if equipo_informante_existente:

                            numero_grupo = (
                                equipo_informante_existente.numero_grupo
                            )

                            errores.append(
                                "Ya registraste un equipo en esta sección. "
                                f"Tu equipo corresponde al Grupo "
                                f"{numero_grupo}."
                            )

                        else:

                            
                            if tipo_socio == "provisional":

                                socio_seleccionado = (
                                    SocioComunitario.objects.create(
                                        nombre_organizacion=(
                                            socio_provisional_nombre
                                        ),
                                        estado_revision="RECIBIDO",
                                        es_provisional=True,
                                        activo=True,
                                        fecha_creacion=timezone.now(),
                                    )
                                )

                            
                            ultimo_numero = (
                                Equipo.objects
                                .filter(
                                    seccion=seccion_bloqueada
                                )
                                .aggregate(
                                    maximo=Max("numero_grupo")
                                )
                                .get("maximo")
                                or 0
                            )

                            numero_grupo = ultimo_numero + 1

                            integrante_informante = (
                                integrantes_validados[0]
                            )

                            nombre_informante = normalizar_nombre(
                                (
                                    f"{integrante_informante['nombres']} "
                                    f"{integrante_informante['apellidos']}"
                                )
                            )

                            
                            equipo = Equipo.objects.create(
                                seccion=seccion_bloqueada,
                                socio_comunitario=socio_seleccionado,
                                numero_grupo=numero_grupo,
                                clave_idempotencia=clave_uuid,
                                informante_nombre=nombre_informante,
                                informante_correo=correo_informante,
                                informante_entra_id=None,
                                estado="Registrado",
                            )

                            
                            IntegranteEquipo.objects.bulk_create(
                                [
                                    IntegranteEquipo(
                                        equipo=equipo,
                                        rut=integrante["rut"],
                                        nombres=integrante["nombres"],
                                        apellidos=integrante["apellidos"],
                                        correo_institucional=integrante["correo"],
                                        es_informante=integrante["es_informante"],
                                    )
                                    for integrante
                                    in integrantes_validados
                                ]
                            )

            except IntegrityError:

                equipo_existente = (
                    Equipo.objects
                    .filter(
                        clave_idempotencia=clave_uuid
                    )
                    .first()
                )

                if equipo_existente:

                    numero_grupo = (
                        equipo_existente.numero_grupo
                    )

                else:

                    errores.append(
                        "No fue posible registrar el equipo. "
                        "Inténtalo nuevamente."
                    )

            
            if not errores:

                messages.success(
                    request,
                    (
                        "Equipo registrado correctamente como "
                        f"Grupo {numero_grupo}."
                    ),
                )

                # POST -> REDIRECT -> GET
                return redirect(
                    "proyectos:acceso_registro_equipos",
                    token=enlace.token,
                )

    
    return render(
        request,
        "proyectos/acceso_registro_equipos.html",
        {
            "enlace": enlace,
            "seccion": enlace.seccion,
            "informante": request.user,
            "errores": errores,
            "datos_formulario": datos_formulario,
            "clave_idempotencia": clave_idempotencia,

            # CDE-46
            "socios_disponibles": socios_disponibles,
        },
    )

def normalizar_nombre(valor):
   
    if not valor:
        return ""

    return " ".join(valor.split())