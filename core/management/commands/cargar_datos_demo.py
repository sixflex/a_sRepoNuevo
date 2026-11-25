"""
Carga datos de demostración desde core/datos_demo/datos_demo_AS.xlsx.

Todo pasa por los servicios del portal (consolidación de planificaciones,
asociación de socios a equipos, revisión de postulaciones, guardado de
respuestas), así los datos quedan igual que si se hubieran ingresado a mano.
No modifica la estructura de la base de datos ni borra nada.

Requisitos: migrate, cargar_formularios y cargar_ruta_docente.
"""
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import openpyxl
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import RequestFactory, override_settings
from django.utils import timezone

from academico.models import (
    Asignatura,
    Campus,
    Carrera,
    Docente,
    Facultad,
    PeriodoAcademico,
    Seccion,
    Sede,
    UnidadAcademica,
)
from cartas.models import CartaEstudiante, SolicitudCarta
from core.validators import normalizar_rut
from encuestas import constantes as c
from encuestas import services as encuestas_services
from encuestas.models import EnlaceFormulario, FormularioVersion
from planificacion.models import FilaPlanificacion, FilaPlanificacionDocente, Planificacion, PlanificacionEnlace
from planificacion.services import actualizar_totales, aprobar_planificacion, consolidar_fila, revisar_planificacion
from proyectos.models import EnlaceRegistroEquipo, Equipo, IntegranteEquipo
from rutas.models import SeccionActividad
from rutas.services import obtener_version_ruta_vigente
from rutas.views import recalcular_avance
from socios.comunas import clave as clave_comuna
from socios import services as socios_services
from socios.constantes import ORIGEN_HISTORICO
from socios.models import (
    ClasificacionSocio,
    Comuna,
    ContactoSocio,
    Convocatoria,
    ParticipacionSocio,
    PostulacionSocio,
    SocioComunitario,
)
from usuarios import entra
from usuarios import services as identidades
from usuarios.entra import get_conector
from usuarios.models import IdentidadInstitucional, Rol

ARCHIVO_POR_DEFECTO = Path(__file__).resolve().parents[2] / "datos_demo" / "datos_demo_AS.xlsx"
CLAVE_DOCENTE = "Docente1234"
CLAVE_COORDINADOR = "Coord1234"


HOJAS_RESPUESTAS = {
    "Resp_Eval_Estudiantes": "EVALUACION_AS_ESTUDIANTES",
    "Resp_Eval_Docentes": "EVALUACION_AS_DOCENTES",
    "Resp_Eval_Socios": "EVALUACION_AS_SOCIOS",
    "Resp_Resumen_Docente": "RESUMEN_IMPLEMENTACION_DOCENTE",
}
FORMULARIO_FICHA = "FICHA_EMPRENDEDORES"
FORMULARIOS_DOCENTE = {"EVALUACION_AS_DOCENTES", "RESUMEN_IMPLEMENTACION_DOCENTE"}


def aware(valor):
    if valor is None or valor == "":
        return None
    if not isinstance(valor, datetime):
        valor = datetime.combine(valor, time(9))
    return timezone.make_aware(valor) if timezone.is_naive(valor) else valor


def fecha(valor):
    return valor.date() if isinstance(valor, datetime) else valor


def texto(valor):
    return "" if valor is None else str(valor).strip()


def si(valor):
    return texto(valor).upper() in ("SI", "SÍ", "TRUE", "1")






CORRECCIONES_COMUNA = {
    "carahue -": ("Carahue", "La Araucanía", Decimal("-38.7114"), Decimal("-73.1647")),
    "el establecimiento se encuentra camino quepe, boroa km 5, temuco": ("Temuco", None, None, None),
    "padre las casas, temuco": ("Padre Las Casas", None, None, None),
    "temuco, araucanía.": ("Temuco", None, None, None),
    "temuco- sector fundo del carmen": ("Temuco", None, None, None),
}


def leer_libro(ruta):
    libro = openpyxl.load_workbook(ruta, data_only=True)
    hojas = {}
    for hoja in libro.worksheets:
        filas = list(hoja.iter_rows(values_only=True))
        if not filas:
            continue

        if sum(1 for v in filas[0] if v not in (None, "")) == 1 and len(filas) > 1 and filas[1][0] is not None:
            filas = filas[1:]
        encabezados = [texto(v) for v in filas[0]]
        hojas[hoja.title] = [
            dict(zip(encabezados, fila)) for fila in filas[1:] if any(v not in (None, "") for v in fila)
        ]
    return hojas


SECCIONES_POR_DOCENTE_LIVIANO = 2
EQUIPOS_POR_SECCION_LIVIANO = 3
SOCIOS_EXTRA_LIVIANO = 20
PARTICIPACIONES_HISTORICAS_LIVIANO = 40
RESPUESTAS_ESTUDIANTES_LIVIANO = 25


def reducir_dataset(datos):
    """
    Muestra pequeña del dataset para un servidor modesto (Render gratis): lo
    justo para recorrer la Ruta (formularios, QR, encuestas, acuerdo, cartas)
    y ver el panel del Coordinador con datos. Mantiene la coherencia entre
    hojas: solo quedan equipos, cartas y respuestas de las secciones elegidas,
    y los socios que esas filas nombran.
    """
    con_ruta = {texto(f["NRC"]) for f in datos["Avance_Ruta"]}



    por_docente = {}
    for fila in sorted(datos["Planificacion"], key=lambda f: (texto(f["RUT"]), texto(f["ASIGNATURA"]), texto(f["SECCIÓN"]))):
        nrc = texto(fila["NRC"])
        if nrc in con_ruta:
            por_docente.setdefault(texto(fila["RUT"]), []).append(nrc)
    nrcs = {nrc for lista in por_docente.values() for nrc in lista[:SECCIONES_POR_DOCENTE_LIVIANO]}


    datos["Planificacion"] = [
        f for f in datos["Planificacion"] if texto(f["NRC"]) in nrcs or texto(f["NRC"]) not in con_ruta
    ]
    unidades = {texto(f["Unidad"]) for f in datos["Planificacion"]}
    datos["Unidades_Planificacion"] = [
        f for f in datos["Unidades_Planificacion"]
        if texto(f["Unidad"]) in unidades or texto(f["Estado planilla"]) != "FINAL"
    ]
    datos["Avance_Ruta"] = [f for f in datos["Avance_Ruta"] if texto(f["NRC"]) in nrcs]

    datos["Equipos"] = [
        f for f in datos["Equipos"]
        if texto(f["NRC"]) in nrcs and int(f["Grupo"]) <= EQUIPOS_POR_SECCION_LIVIANO
    ]
    equipos = {(texto(f["NRC"]), int(f["Grupo"])) for f in datos["Equipos"]}
    datos["Integrantes"] = [f for f in datos["Integrantes"] if (texto(f["NRC"]), int(f["Grupo"])) in equipos]
    datos["Cartas"] = [f for f in datos["Cartas"] if (texto(f["NRC"]), int(f["Grupo"])) in equipos]

    for hoja in HOJAS_RESPUESTAS:
        filas = [
            f for f in datos.get(hoja, [])
            if texto(f["[Contexto] NRC"]) in nrcs
            and (not f.get("[Contexto] Grupo") or (texto(f["[Contexto] NRC"]), int(f["[Contexto] Grupo"])) in equipos)
        ]
        if hoja == "Resp_Eval_Estudiantes":
            filas = filas[:RESPUESTAS_ESTUDIANTES_LIVIANO]
        datos[hoja] = filas

    datos["Participaciones_Historicas"] = datos["Participaciones_Historicas"][:PARTICIPACIONES_HISTORICAS_LIVIANO]
    nombrados = (
        {texto(f["Socio"]) for f in datos["Equipos"]}
        | {texto(f["Socio"]) for f in datos["Participaciones_Historicas"]}
        | {texto(f["Organización"]) for f in datos["Postulaciones"]}
    )
    extra = [f for f in datos["Socios"] if texto(f["Organización"]) not in nombrados][:SOCIOS_EXTRA_LIVIANO]
    datos["Socios"] = [f for f in datos["Socios"] if texto(f["Organización"]) in nombrados] + extra
    return datos


class Command(BaseCommand):
    help = "Carga datos de demostración (docentes, secciones, equipos, socios, Ruta y respuestas) desde el Excel."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=str(ARCHIVO_POR_DEFECTO), help="Ruta del Excel del dataset.")
        parser.add_argument(
            "--liviano", action="store_true",
            help="Carga una muestra pequeña (2 secciones por docente, pocos equipos y socios). Pensado para Render.",
        )

    def handle(self, *args, **options):
        ruta = Path(options["archivo"])
        if not ruta.exists():
            raise CommandError(f"No se encontró el archivo {ruta}.")
        self.datos = leer_libro(ruta)
        if options.get("liviano"):
            self.datos = reducir_dataset(self.datos)
        self.validar_requisitos()


        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            with transaction.atomic():
                self.cargar()

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados."))
        for linea in self.resumen:
            self.stdout.write(f"  {linea}")
        self.stdout.write(
            f"  Docentes: entran con su correo en «Iniciar sesión con Microsoft» o con la clave {CLAVE_DOCENTE}."
        )





    def validar_requisitos(self):
        if obtener_version_ruta_vigente() is None:
            raise CommandError("Falta la Ruta A+S. Ejecuta primero: python manage.py cargar_ruta_docente")
        faltantes = [
            codigo for codigo in [*HOJAS_RESPUESTAS.values(), FORMULARIO_FICHA]
            if self.version(codigo) is None
        ]
        if faltantes:
            raise CommandError(
                f"Faltan formularios publicados ({', '.join(faltantes)}). "
                "Ejecuta primero: python manage.py cargar_formularios"
            )
        nrcs = [texto(f["NRC"]) for f in self.datos["Avance_Ruta"]]
        if Seccion.objects.filter(nrc__in=nrcs, periodo__anio=2026).exists():
            raise CommandError("Los datos de demostración ya están cargados (existen sus NRC en 2026).")

    @staticmethod
    def version(codigo):
        return (
            FormularioVersion.objects.filter(plantilla__codigo=codigo, estado=c.PUBLICADA)
            .order_by("-numero_version").first()
        )





    def cargar(self):
        self.resumen = []
        self.coordinador = self.obtener_coordinador()
        self.request = RequestFactory().post("/")
        self.request.user = self.coordinador
        self.request.META["REMOTE_ADDR"] = "127.0.0.1"

        self.cargar_estructura_academica()
        self.cargar_docentes()
        self.cargar_socios()
        self.cargar_participaciones_historicas()
        self.cargar_planificaciones()
        self.cargar_avance_ruta()
        self.cargar_postulaciones()
        self.cargar_equipos()
        self.cargar_cartas()
        self.cargar_respuestas()

    def obtener_coordinador(self):
        Usuario = get_user_model()
        coordinador = Usuario.objects.filter(groups__name="Coordinador").order_by("id").first()
        if coordinador is None:
            coordinador = Usuario.objects.create_user(
                username="coordinador", password=CLAVE_COORDINADOR,
                correo_institucional="coordinador@uautonoma.cl", first_name="Coordinador", last_name="A+S",
            )
            coordinador.groups.add(Group.objects.get_or_create(name="Coordinador")[0])
        identidades.asegurar_identidad_principal(coordinador)
        return coordinador

    def cargar_estructura_academica(self):
        self.campus = {}
        for fila in self.datos["Sedes_Campus"]:
            sede, _ = Sede.objects.get_or_create(
                nombre=texto(fila["Sede"]), defaults={"ciudad": texto(fila["Ciudad"]), "activo": True},
            )
            campus, _ = Campus.objects.get_or_create(
                sede=sede, nombre=texto(fila["Campus"]),
                defaults={"direccion": texto(fila["Dirección"]), "activo": True},
            )
            self.campus[campus.nombre] = campus

        for fila in self.datos["Facultades_Carreras"]:
            facultad = (
                Facultad.objects.filter(nombre__iexact=texto(fila["Facultad"])).first()
                or Facultad.objects.create(nombre=texto(fila["Facultad"]), activo=True)
            )

            if not Carrera.objects.filter(nombre__iexact=texto(fila["Carrera"])).exists():
                Carrera.objects.create(facultad=facultad, nombre=texto(fila["Carrera"]), activo=True)

        fila = self.datos["Periodos"][0]
        nombre = texto(fila["Nombre"])
        temporada = nombre.split(" (")[0].split()[0]
        periodo = PeriodoAcademico.objects.filter(
            anio=fila["Año"], tipo=texto(fila["Tipo"]), nombre__startswith=temporada,
        ).first()
        if periodo is None:
            periodo = PeriodoAcademico.objects.create(
                anio=fila["Año"], tipo=texto(fila["Tipo"]), nombre=nombre, estado=texto(fila["Estado"]),
            )

        if not periodo.fecha_inicio or not periodo.fecha_fin:
            periodo.fecha_inicio = periodo.fecha_inicio or fecha(fila["Fecha inicio"])
            periodo.fecha_fin = periodo.fecha_fin or fecha(fila["Fecha fin"])
            periodo.save(update_fields=["fecha_inicio", "fecha_fin"])
        self.periodo = periodo

        for fila in self.datos["Asignaturas"]:
            asignatura, _ = Asignatura.objects.get_or_create(
                codigo=texto(fila["Código"]), defaults={"nombre": texto(fila["Asignatura"]), "activo": True},
            )
            asignatura.carreras.add(Carrera.objects.get(nombre__iexact=texto(fila["Carrera"])))

    def cargar_docentes(self):
        Usuario = get_user_model()
        grupo = Group.objects.get_or_create(name="Docente")[0]
        rol = Rol.objects.get_or_create(nombre="Docente")[0]
        for fila in self.datos["Docentes"]:
            correo = texto(fila["Correo institucional"]).lower()
            usuario, creado = Usuario.objects.get_or_create(
                username=correo,
                defaults={
                    "email": correo, "correo_institucional": correo, "rol": rol,
                    "first_name": texto(fila["Nombres"]).split()[0], "last_name": texto(fila["Apellidos"]),
                },
            )
            if creado:
                usuario.set_password(CLAVE_DOCENTE)
                usuario.save()
            usuario.groups.add(grupo)
            Docente.objects.update_or_create(
                rut=normalizar_rut(texto(fila["RUT"])),
                defaults={
                    "usuario": usuario, "nombres": texto(fila["Nombres"]), "apellidos": texto(fila["Apellidos"]),
                    "correo_institucional": correo, "telefono": texto(fila["Teléfono"]), "activo": True,
                },
            )
            identidades.asegurar_identidad_principal(usuario)
        self.resumen.append(f"{len(self.datos['Docentes'])} docentes")
        self.vincular_segunda_cuenta()

    def vincular_segunda_cuenta(self):
        """Un docente con sus dos cuentas (@uautonoma.cl y @cloud.uautonoma.cl) ya unidas."""
        fila = self.datos["Docentes"][0]
        correo = texto(fila["Correo institucional"]).lower()
        usuario = get_user_model().objects.get(username=correo)
        local, dominio = correo.split("@", 1)
        otro = "cloud.uautonoma.cl" if dominio == "uautonoma.cl" else "uautonoma.cl"
        try:
            cuenta = entra.ConectorEntraSimulado().identificar(f"{local}@{otro}")
            identidades.vincular_identidad(usuario, cuenta, IdentidadInstitucional.MANUAL_COORDINADOR)
        except entra.EntraError:
            return
        self.resumen.append(f"Docente con dos cuentas vinculadas: {correo} y {cuenta.correo}")

    def cargar_socios(self):
        comunas = {}


        por_clave = {clave_comuna(c.nombre): c for c in Comuna.objects.all()}

        filas = sorted(self.datos["Comunas"], key=lambda f: texto(f["Comuna"]).lower() in CORRECCIONES_COMUNA)
        for fila in filas:
            original = texto(fila["Comuna"])
            nombre, region, lat, lon = CORRECCIONES_COMUNA.get(
                original.lower(), (original, None, Decimal(str(fila["Latitud"])), Decimal(str(fila["Longitud"]))),
            )

            comuna = por_clave.get(clave_comuna(nombre))
            if comuna is None:
                comuna = Comuna.objects.create(nombre=nombre, region=region or texto(fila["Región"]), activo=True)
                por_clave[clave_comuna(nombre)] = comuna
            if (comuna.lat_centro is None or comuna.lon_centro is None) and lat is not None:
                comuna.lat_centro = lat
                comuna.lon_centro = lon
                comuna.save(update_fields=["lat_centro", "lon_centro"])
            comunas[original] = comuna

        self.socios = {}
        for fila in self.datos["Socios"]:
            clasificacion = (
                ClasificacionSocio.objects.filter(nombre__iexact=texto(fila["Clasificación"])).first()
                or ClasificacionSocio.objects.create(nombre=texto(fila["Clasificación"]), activo=True)
            )
            socio = SocioComunitario.objects.create(
                rut=normalizar_rut(texto(fila["RUT"])) or None,
                nombre_organizacion=texto(fila["Organización"]),
                clasificacion=clasificacion,
                comuna=comunas.get(texto(fila["Comuna"])),
                direccion_exacta=texto(fila["Dirección"]) or None,
                centro_servicio=texto(fila["Centro de servicio"]) or None,
                estado_revision=texto(fila["Estado"]),
                es_provisional=si(fila["Provisional"]),
                activo=True,
                fecha_creacion=timezone.now(),
            )
            ContactoSocio.objects.create(
                socio=socio, nombre=texto(fila["Contacto"]), cargo=texto(fila["Cargo"]) or None,
                correo=texto(fila["Correo"]) or None, telefono=texto(fila["Teléfono"]) or None,
                es_principal=True, activo=True,
            )
            self.socios[socio.nombre_organizacion] = socio
        self.resumen.append(f"{len(self.socios)} socios comunitarios")

    def cargar_participaciones_historicas(self):
        """RF-MIG-02: sin crear secciones ni equipos antiguos."""
        sedes = {s.nombre: s for s in Sede.objects.all()}
        carreras = {c_.nombre.lower(): c_ for c_ in Carrera.objects.all()}
        creadas = 0
        for fila in self.datos["Participaciones_Historicas"]:
            socio = self.socios[texto(fila["Socio"])]
            inicio = fecha(fila["Fecha inicio"])
            ParticipacionSocio.objects.create(
                socio=socio,
                sede=sedes.get(texto(fila["Sede"])),
                carrera=carreras.get(texto(fila["Carrera"]).lower()),
                servicio_realizado=texto(fila["Servicio realizado"]) or None,
                beneficiarios_estimados=fila["Beneficiarios"],
                evaluacion=fila["Evaluación (1-5)"],
                fecha_inicio=inicio,
                fecha_fin=fecha(fila["Fecha fin"]),
                origen=ORIGEN_HISTORICO,
            )

            if aware(inicio) < socio.fecha_creacion:
                socio.fecha_creacion = aware(inicio)
                socio.save(update_fields=["fecha_creacion"])
            creadas += 1
        self.resumen.append(f"{creadas} participaciones históricas (2021-2025)")

    def cargar_planificaciones(self):
        filas_por_unidad = {}
        for fila in self.datos["Planificacion"]:
            filas_por_unidad.setdefault(texto(fila["Unidad"]), []).append(fila)

        aceptadas = observadas = 0
        for unidad_fila in self.datos["Unidades_Planificacion"]:
            carrera = Carrera.objects.get(nombre__iexact=texto(unidad_fila["Carrera"]))
            unidad, _ = UnidadAcademica.objects.get_or_create(
                nombre=texto(unidad_fila["Unidad"]),
                defaults={"tipo": texto(unidad_fila["Tipo"]), "carrera": carrera, "facultad": carrera.facultad,
                          "correo_oficial": texto(unidad_fila["Correo"]), "activo": True},
            )

            campus = self.campus[texto(unidad_fila["Campus"])]
            carrera.campus.add(campus)
            enviada = texto(unidad_fila["Estado planilla"]) == "FINAL"
            emision = aware(datetime(self.periodo.anio, 7, 6, 10))
            enlace = PlanificacionEnlace.objects.create(
                unidad_academica=unidad, campus=campus, periodo=self.periodo,
                destinatario_nombre=texto(unidad_fila["Destinatario"]),
                destinatario_correo=texto(unidad_fila["Correo"]),
                fecha_emision=emision,

                fecha_expiracion=aware(datetime(self.periodo.anio, 8, 7, 23, 59)) if enviada
                else timezone.now() + timedelta(days=14),
                activo=True,
            )
            if not enviada:
                continue

            envio = aware(unidad_fila["Fecha envío"])
            planificacion = Planificacion.objects.create(
                enlace=enlace, estado="FINAL", fecha_guardado=envio, fecha_envio_final=envio,
                filas_recibidas=0, filas_aceptadas=0, filas_observadas=0,
            )
            for numero, fila in enumerate(filas_por_unidad.get(unidad.nombre, []), start=1):
                fila_plan = FilaPlanificacion.objects.create(
                    planificacion=planificacion, numero_fila=numero,
                    facultad_texto=texto(fila["FACULTAD"]), carrera_texto=texto(fila["CARRERA"]),
                    declaracion_as=si(fila["¿La asignatura está declarada como A+S en el Plan de Estudios?"]),
                    nrc=texto(fila["NRC"]), campus_texto=texto(fila["Campus"]), seccion=texto(fila["SECCIÓN"]),
                    asignatura_texto=texto(fila["ASIGNATURA"]), nivel=texto(fila["NIVEL"]),
                    jornada=texto(fila["JORNADA"]), horario=texto(fila["HORARIO"]),
                    estudiantes_planificados=fila["Nº ESTUDIANTES"],
                    posible_socio_texto=texto(fila["POSIBLE SOCIO COMUNITARIO"]) or None,
                    estado_validacion="PENDIENTE",
                )
                FilaPlanificacionDocente.objects.create(
                    fila=fila_plan, rut=texto(fila["RUT"]), nombre=texto(fila["NOMBRE DOCENTE"]),
                    tipo_contrato=texto(fila["TIPO DE CONTRATO"]),
                    capacitado_as=si(fila["YA SE CAPACITÓ ANTERIORMENTE EN A+S"]),
                    correo=texto(fila["CORREO ELECTRÓNICO"]), telefono=texto(fila["CELULAR"]),
                )



            revisar_planificacion(planificacion)
            if not planificacion.filas_observadas:
                aprobar_planificacion(planificacion)
            else:
                for fila_plan in planificacion.filas.filter(estado_validacion="PENDIENTE").order_by("numero_fila"):
                    consolidar_fila(fila_plan)
                actualizar_totales(planificacion)
            Seccion.objects.filter(filas_planificacion_resultantes__planificacion=planificacion).update(fecha_consolidacion=envio)
            aceptadas += planificacion.filas_aceptadas
            observadas += planificacion.filas_observadas
        self.secciones = {s.nrc: s for s in Seccion.objects.filter(periodo=self.periodo)}
        self.resumen.append(
            f"{len(self.datos['Unidades_Planificacion'])} enlaces de planificación; "
            f"{aceptadas} filas aceptadas (secciones) y {observadas} observadas"
        )

    def docente_de(self, seccion):
        return seccion.docentes.order_by("id").first()

    def cargar_avance_ruta(self):
        inicio = aware(datetime(self.periodo.anio, 8, 17, 10))
        hoy = timezone.now() - timedelta(days=1)
        for fila in self.datos["Avance_Ruta"]:
            seccion = self.secciones[texto(fila["NRC"])]
            seccion_ruta = seccion.ruta_asignada
            docente = self.docente_de(seccion)
            completadas = int(fila["Actividades completadas (de 23)"] or 0)
            actividades = list(
                SeccionActividad.objects.filter(seccion_ruta=seccion_ruta).order_by("ruta_actividad__orden")
            )
            paso = (hoy - inicio) / max(len(actividades), 1)
            for indice, actividad in enumerate(actividades[:completadas]):
                actividad.estado = "COMPLETADA"
                actividad.completada_por_docente = docente
                actividad.fecha_completada = inicio + paso * indice
                actividad.save(update_fields=["estado", "completada_por_docente", "fecha_completada"])
            if actividades and completadas >= len(actividades):
                seccion_ruta.estado = "COMPLETADA"
                seccion_ruta.cerrada_por_docente = docente
                seccion_ruta.fecha_cierre = hoy
                seccion_ruta.porcentaje_final = Decimal("100.00")
                seccion_ruta.save(update_fields=["estado", "cerrada_por_docente", "fecha_cierre", "porcentaje_final"])
            else:
                recalcular_avance(seccion_ruta)
        self.resumen.append(f"Ruta A+S con avance en {len(self.datos['Avance_Ruta'])} secciones")

    def cargar_postulaciones(self):
        """RF-SC-01 y RF-SC-02: la convocatoria tiene su enlace y cada postulación su respuesta a la ficha."""
        fila = self.datos["Convocatoria"][0]
        version = self.version(texto(fila["Formulario"]))
        convocatoria = Convocatoria.objects.create(
            formulario_version=version, nombre=texto(fila["Nombre"]), descripcion=texto(fila["Descripción"]),
            fecha_inicio=aware(fila["Fecha inicio"]), fecha_fin=aware(fila["Fecha fin"]), estado=texto(fila["Estado"]),
        )
        enlace = encuestas_services.crear_enlace(version, usuario=self.coordinador, convocatoria=convocatoria)
        respuestas = {
            normalizar_rut(texto(f["RUT"])): f for f in self.datos["Resp_Ficha_Emprendedores"]
        }
        for fila in self.datos["Postulaciones"]:
            socio = self.socios[texto(fila["Organización"])]
            recepcion = aware(fila["Fecha recepción"])
            respuesta = self.guardar_respuesta(version, respuestas[socio.rut], enlace=enlace, fecha_envio=recepcion)
            respuesta.socio = socio
            respuesta.save(update_fields=["socio"])
            postulacion = PostulacionSocio.objects.create(
                convocatoria=convocatoria, respuesta_formulario=respuesta, socio=socio,
                estado="RECIBIDA", fecha_recepcion=recepcion,
            )
            decision = texto(fila["Estado"])
            if decision != "RECIBIDA":
                socios_services.revisar_postulacion(self.request, postulacion, decision, texto(fila["Motivo rechazo"]))
                PostulacionSocio.objects.filter(pk=postulacion.pk).update(fecha_revision=recepcion + timedelta(days=3))
        self.resumen.append(f"1 convocatoria con {len(self.datos['Postulaciones'])} postulaciones")

    def cargar_equipos(self):
        integrantes = {}
        for fila in self.datos["Integrantes"]:
            integrantes.setdefault((texto(fila["NRC"]), int(fila["Grupo"])), []).append(fila)

        conector = get_conector()
        enlaces = {}
        total_integrantes = 0
        for fila in self.datos["Equipos"]:
            seccion = self.secciones[texto(fila["NRC"])]
            registro = aware(fila["Fecha registro"])
            if seccion.pk not in enlaces:
                enlaces[seccion.pk] = EnlaceRegistroEquipo.objects.create(
                    seccion=seccion, creado_por_docente=self.docente_de(seccion), token=uuid.uuid4(),
                    fecha_inicio=registro - timedelta(days=1), fecha_expiracion=registro + timedelta(days=14),
                    activo=True,
                )
            miembros = integrantes[(seccion.nrc, int(fila["Grupo"]))]
            informante = next(m for m in miembros if si(m["Informante"]))
            correo_informante = texto(informante["Correo institucional"]).lower()
            equipo = Equipo.objects.create(
                seccion=seccion, numero_grupo=int(fila["Grupo"]), clave_idempotencia=uuid.uuid4(),
                informante_nombre=f"{texto(informante['Nombres'])} {texto(informante['Apellidos'])}",
                informante_correo=correo_informante,
                informante_entra_id=conector.identificar(correo_informante).oid,
                fecha_registro=registro, estado="Registrado",
            )
            IntegranteEquipo.objects.bulk_create([
                IntegranteEquipo(
                    equipo=equipo, rut=normalizar_rut(texto(m["RUT"])), nombres=texto(m["Nombres"]),
                    apellidos=texto(m["Apellidos"]), correo_institucional=texto(m["Correo institucional"]).lower(),
                    es_informante=si(m["Informante"]),
                )
                for m in miembros
            ])
            total_integrantes += len(miembros)
            socio = self.socios[texto(fila["Socio"])]
            participacion, _ = socios_services.asociar_socio_a_equipo(equipo=equipo, socio=socio, request=None)
            ParticipacionSocio.objects.filter(pk=participacion.pk).update(fecha_inicio=fecha(registro))


        for socio in SocioComunitario.objects.filter(
            estado_revision="APROBADO", participaciones__fecha_fin__isnull=True,
            participaciones__equipo__seccion__periodo=self.periodo,
        ).distinct():
            socios_services.cambiar_estado_socio(self.request, socio, "ASIGNADO")
        self.resumen.append(f"{len(self.datos['Equipos'])} equipos con {total_integrantes} estudiantes")

    def cargar_cartas(self):
        for fila in self.datos["Cartas"]:
            seccion = self.secciones[texto(fila["NRC"])]
            equipo = Equipo.objects.get(seccion=seccion, numero_grupo=int(fila["Grupo"]))
            docente = self.docente_de(seccion)
            estado = texto(fila["Estado"])
            solicitud = SolicitudCarta.objects.create(
                seccion=seccion, campus=seccion.campus, sede=seccion.campus.sede, equipo=equipo,
                socio=equipo.socio_vigente, solicitante_usuario=docente.usuario, docente_derivador=docente,
                solicitante_tipo="DOCENTE", solicitante_nombre=f"{docente.nombres} {docente.apellidos}",
                solicitante_correo=docente.correo_institucional,
                institucion_receptora=texto(fila["Institución receptora"]),
                persona_receptora=texto(fila["Persona receptora"]), cargo_receptor=texto(fila["Cargo receptor"]),
                estado=estado, motivo_observacion=texto(fila["Motivo observación"]) or None,
                fecha_solicitud=aware(fila["Fecha solicitud"]),
                fecha_aprobacion=aware(fila["Fecha solicitud"]) + timedelta(days=2) if estado == "APROBADA" else None,
            )
            CartaEstudiante.objects.bulk_create([
                CartaEstudiante(solicitud=solicitud, nombre=f"{i.nombres} {i.apellidos}", rut=i.rut, orden=orden)
                for orden, i in enumerate(equipo.integrantes.order_by("id")[:6], start=1)
            ])
        self.resumen.append(f"{len(self.datos['Cartas'])} solicitudes de carta")





    def cargar_respuestas(self):
        enlaces_creados = []
        total = 0
        for hoja, codigo in HOJAS_RESPUESTAS.items():
            version = self.version(codigo)
            enlaces = {}
            for fila in self.datos.get(hoja, []):
                seccion = self.secciones[texto(fila["[Contexto] NRC"])]
                equipo = None
                if fila.get("[Contexto] Grupo"):
                    equipo = Equipo.objects.get(seccion=seccion, numero_grupo=int(fila["[Contexto] Grupo"]))
                clave = (seccion.pk, equipo.pk if equipo else None)

                if clave not in enlaces:
                    contexto = {"seccion": seccion}
                    if equipo:
                        contexto.update(equipo=equipo, socio=equipo.socio_vigente)
                    enlaces[clave] = encuestas_services.crear_enlace(version, usuario=self.coordinador, **contexto)
                    enlaces_creados.append(enlaces[clave].pk)
                respuesta = self.guardar_respuesta(
                    version, fila, enlace=enlaces[clave], fecha_envio=aware(fila["Marca temporal"]),
                )
                carreras = list(seccion.carreras.all()[:2])
                respuesta.carrera = carreras[0] if len(carreras) == 1 else None
                if codigo in FORMULARIOS_DOCENTE:
                    respuesta.docente = self.docente_de(seccion)
                respuesta.save(update_fields=["carrera", "docente"])
                total += 1

        EnlaceFormulario.objects.filter(pk__in=enlaces_creados).update(activo=False, fecha_expiracion=timezone.now())
        self.resumen.append(f"{total} respuestas de encuestas (más {len(self.datos['Postulaciones'])} fichas)")

    def guardar_respuesta(self, version, fila, enlace, fecha_envio):
        """Convierte una fila con formato de exportación de Forms en una respuesta del portal."""
        bloques, preguntas = encuestas_services.cargar_estructura(version)
        columnas = encuestas_services.columnas_por_pregunta(preguntas, fila.keys())
        valores, otros, seleccion, _ = encuestas_services.valores_desde_celdas(
            preguntas, {pregunta_id: fila.get(columna) for pregunta_id, columna in columnas.items()},
        )
        _, visibles, _ = encuestas_services.calcular_visibilidad(bloques, preguntas, seleccion)
        return encuestas_services.guardar_respuesta(
            version, preguntas, valores, otros, visibles, seleccion, enlace=enlace, fecha_envio=fecha_envio,
        )
