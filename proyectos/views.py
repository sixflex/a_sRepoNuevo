from datetime import datetime, time, timedelta
import base64
from io import BytesIO
from urllib import request
import qrcode
import uuid
from django.db import transaction, IntegrityError
from django.db.models import Max, Q
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from socios.comunas import nombres_comunas
from socios.models import SocioComunitario
from socios.services import asociar_socio_a_equipo, historial_socios_equipo, socios_elegidos_seccion, socios_para_registro_equipos

from usuarios.decorators import coordinador_required, docente_required
from usuarios.services import correo_de_sesion, correos_de_usuario, oid_de_sesion
from core.textos import nombre_persona
from core.validators import es_rut_valido, normalizar_rut

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
    Etiqueta,
    IntegranteEtiqueta,
)

from auditoria.services import registrar_auditoria
from django.core.exceptions import PermissionDenied

from .models import EnlaceRegistroEquipo
from . import integrantes_equipo, registro_socio, trabajo_socio
def _crear_enlaces_planificacion(request):
    """
    Genera un enlace individual por cada unidad académica marcada y cada campus
    marcado donde esa unidad imparte carreras (RF-ACA-02: unidad, campus, sede
    y período; oferta en CarreraCampus). El destinatario viene del correo
    oficial de la unidad y se puede editar. Si algo está mal no se crea
    ninguno, para no dejar envíos a medias.
    """
    from planificacion.services import campus_de_unidad

    volver = redirect("proyectos:gestionar_enlaces")
    unidad_ids = [valor for valor in request.POST.getlist("unidades") if valor.isdigit()]
    campus_ids = [valor for valor in request.POST.getlist("campus") if valor.isdigit()]
    periodo_id = request.POST.get("periodo")
    fecha_expiracion = parse_date(request.POST.get("fecha_expiracion") or "")

    if not unidad_ids:
        messages.error(request, "Marque al menos una unidad académica.")
        return volver
    if not campus_ids:
        messages.error(request, "Marque al menos un campus.")
        return volver
    if not (periodo_id and fecha_expiracion):
        messages.error(request, "Debe completar el período y la fecha límite de vigencia.")
        return volver


    fecha_expiracion_dt = timezone.make_aware(datetime.combine(fecha_expiracion, time.max))
    if fecha_expiracion_dt <= timezone.now():
        messages.error(request, "La fecha de expiración debe ser posterior al momento actual.")
        return volver

    periodo = get_object_or_404(PeriodoAcademico, pk=periodo_id)
    campus_marcados = list(
        Campus.objects.filter(pk__in=campus_ids, activo=True)
        .select_related("sede")
        .order_by("sede__nombre", "nombre")
    )
    unidades = {
        str(unidad.pk): unidad
        for unidad in UnidadAcademica.objects.filter(pk__in=unidad_ids, activo=True)
    }

    envios = []
    errores = []
    omitidas = []
    for unidad_id in unidad_ids:
        unidad = unidades.get(unidad_id)
        if unidad is None:
            errores.append("Una de las unidades marcadas no existe o está inactiva.")
            continue
        nombre = (request.POST.get(f"nombre_{unidad_id}") or "").strip()
        correo = (request.POST.get(f"correo_{unidad_id}") or "").strip()
        if not nombre or not correo:
            errores.append(f"{unidad.nombre}: falta el nombre o el correo del destinatario.")
            continue
        try:
            validate_email(correo)
        except ValidationError:
            errores.append(f"{unidad.nombre}: el correo «{correo}» no tiene un formato válido.")
            continue
        campus_unidad = set(campus_de_unidad(unidad).values_list("pk", flat=True))
        if not campus_unidad:
            errores.append(
                f"{unidad.nombre}: su carrera no tiene campus registrados. "
                "Márquelos en Gestión académica > Carreras."
            )
            continue
        destinos = [campus for campus in campus_marcados if campus.pk in campus_unidad]
        if not destinos:
            omitidas.append(unidad.nombre)
            continue
        envios.extend((unidad, campus, nombre, correo) for campus in destinos)

    if errores:
        for error in errores:
            messages.error(request, error)
        messages.info(request, "No se generó ningún enlace. Corrija los datos y vuelva a intentarlo.")
        return volver

    enviados, sin_correo = [], []
    for unidad, campus, nombre, correo in envios:
        enlace = PlanificacionEnlace.objects.create(
            unidad_academica=unidad,
            campus=campus,
            periodo=periodo,
            destinatario_nombre=nombre,
            destinatario_correo=correo,
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
                "fecha_expiracion": enlace.fecha_expiracion.isoformat(),
                "activo": enlace.activo,
            },
        )
        try:
            enviado = enviar_correo_planificacion(request, enlace, reenvio=False)
        except Exception:
            enviado = False
        (enviados if enviado else sin_correo).append(f"{unidad.nombre} · {campus.nombre} ({correo})")

    if enviados:
        messages.success(
            request,
            f"Se generaron y enviaron {len(enviados)} enlace(s): " + "; ".join(enviados) + ".",
        )
    if sin_correo:
        messages.warning(
            request,
            "Enlace(s) generado(s) pero no se pudo enviar el correo a: "
            + "; ".join(sin_correo)
            + ". Puede copiarlos o reenviarlos desde la lista.",
        )
    if omitidas:
        messages.info(
            request,
            "No se envió enlace a " + ", ".join(omitidas)
            + ": sus carreras no se imparten en los campus marcados.",
        )
    return volver


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

        return _crear_enlaces_planificacion(request)


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

    unidades = list(
        UnidadAcademica.objects.filter(activo=True)
        .select_related("facultad", "carrera__facultad")
        .order_by("tipo", "nombre")
    )

    from planificacion.services import campus_de_unidad

    for unidad in unidades:
        unidad.campus_imparte = list(campus_de_unidad(unidad).values_list("pk", "nombre"))
        unidad.campus_imparte_ids = [pk for pk, _ in unidad.campus_imparte]
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


    if not seccion.docentes.filter(pk=docente.pk).exists():
        raise PermissionDenied


    enlace = (
        EnlaceRegistroEquipo.objects
        .filter(seccion=seccion)
        .order_by("-fecha_inicio", "-id")
        .first()
    )

    if request.method == "POST":
        accion = request.POST.get("accion")


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
            "total_socios_elegidos": socios_elegidos_seccion(seccion).count(),
        },
    )

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
                    "Este formulario es solo para estudiantes. "
                    "Ingresaste con una cuenta que no es de estudiante: "
                    "cierra sesión e ingresa con tu correo "
                    "@cloud.uautonoma.cl, o abre el enlace en una "
                    "ventana de incógnito."
                ),
                "es_estudiante": False,
                "hide_sidebar": True,
            },
            status=403,
        )





    mis_correos = {
        correo.lower()
        for correo in correos_de_usuario(request.user) | {correo_de_sesion(request) or ""}
        if correo
    }
    equipo_registrado = None
    if mis_correos:
        filtro_registro = Q(pk__in=[])
        for correo in mis_correos:
            filtro_registro |= Q(integrantes__correo_institucional__iexact=correo)
        equipo_registrado = (
            Equipo.objects
            .filter(filtro_registro, seccion=enlace.seccion)
            .con_socio_vigente()
            .prefetch_related("integrantes")
            .distinct()
            .first()
        )
    if equipo_registrado is not None:
        return _mi_equipo(request, enlace, equipo_registrado, mis_correos)

    if not enlace.activo:
        return render(
            request,
            "proyectos/registro_equipos_no_disponible.html",
            {
                "motivo": "El formulario de registro se encuentra cerrado.",
                "hide_sidebar": True,
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
                "hide_sidebar": True,
            },
            status=403,
        )



    socios_disponibles, socios_de_la_seccion = socios_para_registro_equipos(
        enlace.seccion
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
        socio_nuevo = registro_socio.leer(request.POST)
        datos_formulario.update(socio_nuevo)
        socio_nuevo_limpio = {}

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
                        socios_disponibles
                        .filter(pk=socio_comunitario_id)
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


            socio_nuevo_limpio, errores_socio = registro_socio.validar(socio_nuevo)
            errores.extend(errores_socio)

        
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

                nombres = nombre_persona(
                    nombres_declarados
                )

                apellidos = nombre_persona(
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
                    if not es_rut_valido(rut):
                        errores.append(
                            f"Integrante {i}: el RUT ingresado "
                            "no es válido."
                        )

                    rut_normalizado = normalizar_rut(rut)

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

        

        correo_informante = correo_de_sesion(request) or ""


        filtro_mis_equipos = Q(pk__in=[])
        for correo_propio in correos_de_usuario(request.user) | {correo_informante}:
            if correo_propio:
                filtro_mis_equipos |= Q(informante_correo__iexact=correo_propio)

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
                    filtro_mis_equipos,
                    seccion=enlace.seccion,
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
                                filtro_mis_equipos,
                                seccion=seccion_bloqueada,
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

                                socio_seleccionado = registro_socio.crear(
                                    socio_provisional_nombre,
                                    socio_nuevo_limpio,
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

                            nombre_informante = nombre_persona(
                                (
                                    f"{integrante_informante['nombres']} "
                                    f"{integrante_informante['apellidos']}"
                                )
                            )

                            


                            equipo = Equipo.objects.create(
                                seccion=seccion_bloqueada,
                                numero_grupo=numero_grupo,
                                clave_idempotencia=clave_uuid,
                                informante_nombre=nombre_informante,
                                informante_correo=correo_informante,
                                informante_entra_id=oid_de_sesion(request),
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

                            asociar_socio_a_equipo(
                                equipo=equipo,
                                socio=socio_seleccionado,
                                request=request,
                            )

            except ValidationError as error:

                errores.extend(error.messages)

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
            "correo_informante": correo_de_sesion(request),
            "errores": errores,
            "datos_formulario": datos_formulario,
            "clave_idempotencia": clave_idempotencia,


            "socios_disponibles": socios_disponibles,
            "socios_de_la_seccion": socios_de_la_seccion,
            "comunas": nombres_comunas(),
            "clasificaciones": registro_socio.clasificaciones(),
            "hide_sidebar": True,
        },
    )

def _mi_equipo(request, enlace, equipo, mis_correos):
    """
    Página del equipo ya registrado: sus datos y el trabajo con el socio
    (beneficiarios, servicio, evaluación y comentario), que cualquier
    integrante completa o corrige durante el semestre.
    """
    participacion = equipo.participaciones_vigentes[0] if equipo.participaciones_vigentes else None


    guardando = request.method == "POST" and request.POST.get("accion") == "trabajo_socio"
    form = trabajo_socio.formulario(participacion, request.POST if guardando else None)
    if guardando and participacion is not None and form.is_valid():
        trabajo_socio.guardar(participacion, form, request)
        messages.success(request, "Se guardó el trabajo con el socio. Pueden corregirlo cuando quieran.")
        return redirect("proyectos:acceso_registro_equipos", token=enlace.token)

    return render(
        request,
        "proyectos/registro_equipos_listo.html",
        {
            "seccion": enlace.seccion,
            "equipo": equipo,
            "participacion": participacion,
            "form_trabajo": form,
            "trabajo_completo": trabajo_socio.completo(participacion),
            "lo_registre_yo": equipo.informante_correo.lower() in mis_correos,
            "hide_sidebar": True,
        },
    )


def normalizar_nombre(valor):
   
    if not valor:
        return ""

    return " ".join(valor.split())

@docente_required
def gestionar_equipos_seccion(request, seccion_id):
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

    
    if not seccion.docentes.filter(pk=docente.pk).exists():
        raise PermissionDenied

    equipos = (
        Equipo.objects
        .filter(seccion=seccion)
        .con_socio_vigente()
        .prefetch_related("integrantes")
        .order_by("numero_grupo")
    )

    equipos = list(equipos)
    resumen = {
        "equipos": len(equipos),
        "estudiantes": sum(len(equipo.integrantes.all()) for equipo in equipos),
        "con_socio": sum(1 for equipo in equipos if equipo.socio_vigente),
    }

    return render(
        request,
        "proyectos/gestionar_equipos_seccion.html",
        {
            "seccion": seccion,
            "equipos": equipos,
            "resumen": resumen,
        },
    )

@docente_required
def gestionar_equipo(request, equipo_id):
    docente = get_object_or_404(
        Docente,
        usuario=request.user,
        activo=True,
    )

    equipo = get_object_or_404(
        Equipo.objects.select_related(
            "seccion",
            "seccion__asignatura",
            "seccion__periodo",
            "seccion__campus",
        ).prefetch_related(
            "integrantes__etiquetas_asignadas__etiqueta",
        ),
        pk=equipo_id,
    )

    
    if not equipo.seccion.docentes.filter(pk=docente.pk).exists():
        raise PermissionDenied

    if request.method == "POST":
        accion = request.POST.get("accion", "").strip()

        
        if accion == "gestionar_etiquetas":
            integrante_id = request.POST.get(
                "integrante_id",
                "",
            ).strip()

            integrante = get_object_or_404(
                IntegranteEquipo,
                pk=integrante_id,
                equipo=equipo,
            )

            etiquetas_ids = request.POST.getlist("etiquetas")

            
            etiquetas_validas = list(
                Etiqueta.objects.filter(
                    id__in=etiquetas_ids,
                    activo=True,
                )
            )

            ids_validos = {
                str(etiqueta.id)
                for etiqueta in etiquetas_validas
            }

            ids_recibidos = {
                str(etiqueta_id)
                for etiqueta_id in etiquetas_ids
            }

            if ids_validos != ids_recibidos:
                messages.error(
                    request,
                    "Una o más etiquetas seleccionadas no son válidas.",
                )

                return redirect(
                    "proyectos:gestionar_equipo",
                    equipo_id=equipo.id,
                )

            with transaction.atomic():

                IntegranteEtiqueta.objects.filter(
                    integrante=integrante,
                ).exclude(
                    etiqueta_id__in=ids_validos,
                ).delete()


                for etiqueta in etiquetas_validas:
                    IntegranteEtiqueta.objects.get_or_create(
                        integrante=integrante,
                        etiqueta=etiqueta,
                        defaults={
                            "asignado_por_docente": docente,
                        },
                    )

            messages.success(
                request,
                "Las etiquetas del integrante fueron actualizadas "
                "correctamente.",
            )

            return redirect(
                "proyectos:gestionar_equipo",
                equipo_id=equipo.id,
            )

        
        elif accion == "agregar_integrante":

            errores_integrante = integrantes_equipo.agregar(equipo, request.POST, request)
            for error in errores_integrante:
                messages.error(request, error)
            if not errores_integrante:
                messages.success(request, "Se agregó el integrante al equipo.")
            return redirect("proyectos:gestionar_equipo", equipo_id=equipo.id)

        elif accion == "quitar_integrante":


            integrante = get_object_or_404(
                IntegranteEquipo, pk=request.POST.get("integrante_id", "").strip() or 0, equipo=equipo,
            )
            error = integrantes_equipo.quitar(equipo, integrante, request)
            if error:
                messages.error(request, error)
            else:
                messages.success(request, f"Se quitó a {integrante.nombres} {integrante.apellidos} del equipo.")
            return redirect("proyectos:gestionar_equipo", equipo_id=equipo.id)

        elif accion == "trabajo_socio":


            participacion = equipo.participaciones_socios.filter(fecha_fin__isnull=True).first()
            form_trabajo = trabajo_socio.formulario(participacion, request.POST)
            if participacion is None:
                messages.error(request, "El equipo no tiene un socio asociado.")
            elif form_trabajo.is_valid():
                trabajo_socio.guardar(participacion, form_trabajo, request)
                messages.success(request, "Se guardó el trabajo con el socio.")
            else:
                for errores_campo in form_trabajo.errors.values():
                    messages.error(request, errores_campo[0])
            return redirect("proyectos:gestionar_equipo", equipo_id=equipo.id)

        elif accion == "corregir_integrante":
            integrante_id = request.POST.get(
                "integrante_id",
                "",
            ).strip()

            integrante = get_object_or_404(
                IntegranteEquipo,
                pk=integrante_id,
                equipo=equipo,
            )

            nombres = nombre_persona(
                request.POST.get("nombres", "")
            )

            apellidos = nombre_persona(
                request.POST.get("apellidos", "")
            )

            correo = (
                request.POST.get("correo", "")
                .strip()
                .lower()
            )

            errores_integrante = []

            
            if not nombres:
                errores_integrante.append(
                    "Los nombres son obligatorios."
                )

            elif len(nombres) > 120:
                errores_integrante.append(
                    "Los nombres no pueden superar los 120 caracteres."
                )

           
            if not apellidos:
                errores_integrante.append(
                    "Los apellidos son obligatorios."
                )

            elif len(apellidos) > 120:
                errores_integrante.append(
                    "Los apellidos no pueden superar los 120 caracteres."
                )

            
            if not correo:
                errores_integrante.append(
                    "El correo institucional es obligatorio."
                )

            else:
                try:
                    validate_email(correo)

                except ValidationError:
                    errores_integrante.append(
                        "El correo institucional no tiene un formato válido."
                    )

            
            if correo:
                correo_repetido = (
                    IntegranteEquipo.objects
                    .filter(
                        equipo=equipo,
                        correo_institucional__iexact=correo,
                    )
                    .exclude(pk=integrante.pk)
                    .exists()
                )

                if correo_repetido:
                    errores_integrante.append(
                        "El correo institucional ya pertenece a otro "
                        "integrante del equipo."
                    )

            
            if integrante.es_informante:
                correo_informante = (
                    equipo.informante_correo or ""
                ).strip().lower()

                if correo != correo_informante:
                    errores_integrante.append(
                        "No se puede cambiar el correo del informante "
                        "por uno diferente al correo registrado "
                        "en el equipo."
                    )

            
            if errores_integrante:
                for error in errores_integrante:
                    messages.error(
                        request,
                        error,
                    )

                return redirect(
                    "proyectos:gestionar_equipo",
                    equipo_id=equipo.id,
                )

            
            integrante.nombres = nombres
            integrante.apellidos = apellidos
            integrante.correo_institucional = correo

            integrante.save(
                update_fields=[
                    "nombres",
                    "apellidos",
                    "correo_institucional",
                ]
            )

            
            if integrante.es_informante:
                equipo.informante_nombre = nombre_persona(
                    f"{nombres} {apellidos}"
                )

                equipo.save(
                    update_fields=[
                        "informante_nombre",
                    ]
                )

            messages.success(
                request,
                "Los datos del integrante fueron corregidos correctamente.",
            )

            return redirect(
                "proyectos:gestionar_equipo",
                equipo_id=equipo.id,
            )

        
        elif accion == "cambiar_socio":
            socio_nuevo_id = request.POST.get(
                "socio_comunitario",
                "",
            ).strip()

            motivo = normalizar_nombre(
                request.POST.get("motivo", "")
            )

            
            if not socio_nuevo_id:
                messages.error(
                    request,
                    "Debes seleccionar un Socio Comunitario.",
                )

                return redirect(
                    "proyectos:gestionar_equipo",
                    equipo_id=equipo.id,
                )

            if not motivo:
                messages.error(
                    request,
                    "Debes indicar el motivo del cambio.",
                )

                return redirect(
                    "proyectos:gestionar_equipo",
                    equipo_id=equipo.id,
                )

            if len(motivo) > 255:
                messages.error(
                    request,
                    "El motivo del cambio no puede superar "
                    "los 255 caracteres.",
                )

                return redirect(
                    "proyectos:gestionar_equipo",
                    equipo_id=equipo.id,
                )

            

            socios_permitidos, _ = socios_para_registro_equipos(equipo.seccion)
            socio_nuevo = socios_permitidos.filter(pk=socio_nuevo_id).first() if socio_nuevo_id.isdigit() else None

            if socio_nuevo is None:
                messages.error(
                    request,
                    "El Socio Comunitario seleccionado no está disponible.",
                )

                return redirect(
                    "proyectos:gestionar_equipo",
                    equipo_id=equipo.id,
                )



            try:
                _, creada = asociar_socio_a_equipo(
                    equipo=equipo,
                    socio=socio_nuevo,
                    docente=docente,
                    motivo=motivo,
                    request=request,
                )
            except ValidationError as error:
                messages.error(request, error.messages[0])

                return redirect(
                    "proyectos:gestionar_equipo",
                    equipo_id=equipo.id,
                )

            if not creada:
                messages.warning(
                    request,
                    "El equipo ya se encuentra asociado a ese "
                    "Socio Comunitario.",
                )

                return redirect(
                    "proyectos:gestionar_equipo",
                    equipo_id=equipo.id,
                )

            messages.success(
                request,
                "El Socio Comunitario del equipo fue actualizado "
                "correctamente.",
            )

            return redirect(
                "proyectos:gestionar_equipo",
                equipo_id=equipo.id,
            )


    integrantes = (
        equipo.integrantes
        .all()
        .order_by("id")
    )

    etiquetas = (
        Etiqueta.objects
        .filter(
            activo=True
        )
        .order_by(
            "nombre"
        )
    )



    socios_disponibles, socios_de_la_seccion = socios_para_registro_equipos(equipo.seccion)
    socio_actual = equipo.socio_vigente
    if socio_actual is not None:
        socios_disponibles = socios_disponibles.exclude(pk=socio_actual.pk)



    historial_socios = historial_socios_equipo(equipo)


    participaciones_socio = (
        equipo.participaciones_socios
        .select_related("socio")
        .order_by("-fecha_inicio", "-pk")
    )
    participacion_vigente = next((p for p in participaciones_socio if p.vigente), None)

    return render(
        request,
        "proyectos/gestionar_equipo.html",
        {
            "equipo": equipo,
            "integrantes": integrantes,
            "etiquetas": etiquetas,
            "socios_disponibles": socios_disponibles,
            "socios_de_la_seccion": socios_de_la_seccion,
            "historial_socios": historial_socios,
            "participaciones_socio": participaciones_socio,
            "maximo_integrantes": integrantes_equipo.MAXIMO,
            "form_trabajo": trabajo_socio.formulario(participacion_vigente),
            "participacion_vigente": participacion_vigente,
            "trabajo_completo": trabajo_socio.completo(participacion_vigente),
        },
    )





@coordinador_required
def catalogo_proyectos(request):
    """Proyectos A+S en curso este semestre y cerrados, con filtros. Ver proyectos/catalogo.py."""
    from urllib.parse import urlencode

    from django.core.paginator import Paginator

    from academico.models import Carrera, PeriodoAcademico, Sede
    from socios.models import ParticipacionSocio

    from . import catalogo

    filtros = catalogo.leer_filtros(request.GET)
    elegidos, totales = catalogo.proyectos(filtros)
    pagina = Paginator(elegidos, 24).get_page(request.GET.get("pagina"))


    otros = {k: v for k, v in filtros.items() if v and k != "estado"}
    anios = sorted(
        set(PeriodoAcademico.objects.values_list("anio", flat=True))
        | {f.year for f in ParticipacionSocio.objects.trabajadas().filter(periodo__isnull=True).exclude(fecha_inicio=None).values_list("fecha_inicio", flat=True)},
        reverse=True,
    )
    return render(request, "proyectos/catalogo.html", {
        "filtros": filtros,
        "totales": totales,
        "pagina": pagina,
        "tarjetas": [catalogo.tarjeta(p) for p in pagina.object_list],
        "hay_filtros": bool(otros),
        "qs_en_curso": urlencode(otros),
        "qs_cerrados": urlencode({**otros, "estado": catalogo.CERRADOS}),
        "qs_pagina": urlencode({**otros, "estado": filtros["estado"]}),
        "anios": anios,
        "sedes": Sede.objects.order_by("nombre"),
        "carreras": Carrera.objects.filter(participaciones_socios__in=ParticipacionSocio.objects.trabajadas()).distinct().order_by("nombre"),
        "CERRADOS": catalogo.CERRADOS,
    })
