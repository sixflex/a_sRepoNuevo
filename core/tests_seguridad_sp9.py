from datetime import timedelta
from pathlib import Path
import re
import uuid

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
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
from archivos.models import RecursoRepositorio
from archivos.services import guardar_archivo
from encuestas.models import EnlaceFormulario, FormularioPlantilla, FormularioVersion
from planificacion.models import Planificacion, PlanificacionEnlace
from publico.models import ConfiguracionPortal
from socios.models import Comuna, ContactoSocio, ParticipacionSocio, SocioComunitario
from usuarios.models import Rol, Usuario


class SeguridadYPrivacidadSP9Tests(TestCase):
    def setUp(self):
        self.rol_coord, _ = Rol.objects.get_or_create(nombre="COORDINADOR")
        self.rol_doc, _ = Rol.objects.get_or_create(nombre="DOCENTE")
        self.grupo_coord, _ = Group.objects.get_or_create(name="Coordinador")
        self.grupo_doc, _ = Group.objects.get_or_create(name="Docente")

        self.coordinador = Usuario.objects.create_user(
            username="coord_seg",
            email="coord_seg@uautonoma.cl",
            password="PasswordSegura123!",
            rol=self.rol_coord,
        )
        self.coordinador.groups.add(self.grupo_coord)

        self.docente_user_1 = Usuario.objects.create_user(
            username="docente_1",
            email="docente1@uautonoma.cl",
            password="PasswordSegura123!",
            rol=self.rol_doc,
        )
        self.docente_user_1.groups.add(self.grupo_doc)

        self.docente_user_2 = Usuario.objects.create_user(
            username="docente_2",
            email="docente2@uautonoma.cl",
            password="PasswordSegura123!",
            rol=self.rol_doc,
        )
        self.docente_user_2.groups.add(self.grupo_doc)

        self.sede = Sede.objects.create(nombre="Sede Prueba", ciudad="Temuco", activo=True)
        self.campus = Campus.objects.create(nombre="Campus Central", sede=self.sede, activo=True)
        self.facultad = Facultad.objects.create(nombre="Facultad Ingeniería", codigo="FI", activo=True)
        self.carrera = Carrera.objects.create(
            nombre="Ingeniería Civil", facultad=self.facultad, codigo="IC", activo=True
        )
        self.unidad = UnidadAcademica.objects.create(
            nombre="UA Ingeniería",
            tipo="CARRERA",
            facultad=self.facultad,
            carrera=self.carrera,
            activo=True,
        )
        self.periodo = PeriodoAcademico.objects.create(
            nombre="2026-2", anio=2026, tipo="SEMESTRAL", estado="Activo"
        )
        self.asignatura = Asignatura.objects.create(nombre="Taller A+S", codigo="TAS101", activo=True)

        self.docente_1 = Docente.objects.create(
            rut="11111111-1",
            nombres="Docente",
            apellidos="Uno",
            correo_institucional="docente1@uautonoma.cl",
            usuario=self.docente_user_1,
            activo=True,
        )
        self.docente_2 = Docente.objects.create(
            rut="22222222-2",
            nombres="Docente",
            apellidos="Dos",
            correo_institucional="docente2@uautonoma.cl",
            usuario=self.docente_user_2,
            activo=True,
        )

        self.seccion_1 = Seccion.objects.create(
            asignatura=self.asignatura,
            periodo=self.periodo,
            campus=self.campus,
            seccion="01",
            nrc="10001",
            estado="ACTIVA",
        )
        self.seccion_1.docentes.add(self.docente_1)

        self.seccion_2 = Seccion.objects.create(
            asignatura=self.asignatura,
            periodo=self.periodo,
            campus=self.campus,
            seccion="02",
            nrc="10002",
            estado="ACTIVA",
        )
        self.seccion_2.docentes.add(self.docente_2)

    # ------------------------------------------------------------------
    # CDE-379 / CDE-381: HTTPS y redirección HTTP
    # ------------------------------------------------------------------
    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True, ALLOWED_HOSTS=["testserver"])
    def test_cde379_cde381_redirige_http_a_https_en_produccion(self):
        client = Client()
        resp = client.get("/", secure=False)
        self.assertEqual(resp.status_code, 301)
        self.assertTrue(resp["Location"].startswith("https://"))

    # ------------------------------------------------------------------
    # CDE-382 / CDE-383: Permisos de Coordinador y Docente
    # ------------------------------------------------------------------
    def test_cde382_cde383_permisos_coordinador_vs_docente(self):
        client = Client()

        # Anónimo redirige a login
        resp_anon = client.get(reverse("core:coordinacion"))
        self.assertEqual(resp_anon.status_code, 302)

        # Docente no puede entrar a rutas de Coordinador (403)
        client.force_login(self.docente_user_1)
        self.assertEqual(client.get(reverse("core:coordinacion")).status_code, 403)
        self.assertEqual(client.get(reverse("core:exportar_indicadores")).status_code, 403)
        self.assertEqual(client.get(reverse("archivos:repositorio")).status_code, 403)
        self.assertEqual(client.get(reverse("publico:configurar_portal")).status_code, 403)

        # Docente sí entra a su panel
        self.assertEqual(client.get(reverse("core:inicio_docente")).status_code, 200)

        # Coordinador sí entra a su panel
        client.force_login(self.coordinador)
        self.assertEqual(client.get(reverse("core:coordinacion")).status_code, 200)

    # ------------------------------------------------------------------
    # CDE-384 / CDE-386: Aislamiento entre secciones y URL manipulada
    # ------------------------------------------------------------------
    def test_cde384_cde386_aislamiento_secciones_y_url_manipulada(self):
        client = Client()
        client.force_login(self.docente_user_1)

        # Puede ver su propia sección
        url_propia = reverse("core:detalle_seccion", args=[self.seccion_1.id])
        self.assertEqual(client.get(url_propia).status_code, 200)

        # No puede ver la sección del docente 2 manipulando el ID en la URL
        url_ajena = reverse("core:detalle_seccion", args=[self.seccion_2.id])
        self.assertEqual(client.get(url_ajena).status_code, 403)

        # ID inexistente devuelve 404
        url_inexistente = reverse("core:detalle_seccion", args=[999999])
        self.assertEqual(client.get(url_inexistente).status_code, 404)

    # ------------------------------------------------------------------
    # CDE-385 / CDE-386: Vigencia de enlaces y tokens manipulados
    # ------------------------------------------------------------------
    def test_cde385_cde386_vigencia_enlaces_y_tokens_manipulados(self):
        client = Client()
        ahora = timezone.now()

        # 1. Enlace de planificación expirado
        enlace_plan = PlanificacionEnlace.objects.create(
            unidad_academica=self.unidad,
            campus=self.campus,
            periodo=self.periodo,
            destinatario_nombre="Director Carrera",
            destinatario_correo="director@uautonoma.cl",
            fecha_emision=ahora - timedelta(days=5),
            fecha_expiracion=ahora - timedelta(hours=1),
            activo=True,
        )
        url_plan = reverse("planificacion:formulario_tabular_as", args=[enlace_plan.token])
        resp_get = client.get(url_plan)
        self.assertEqual(resp_get.status_code, 200)
        self.assertFalse(resp_get.context["vigente"])
        self.assertFalse(resp_get.context["editable"])

        # Intento de envío POST en enlace expirado no crea planificación y mantiene vigente=False
        resp_post = client.post(url_plan, data={"enviar_final": "1"})
        self.assertEqual(resp_post.status_code, 200)
        self.assertFalse(Planificacion.objects.filter(enlace=enlace_plan).exists())

        # 2. Enlace de encuesta expirado
        plantilla = FormularioPlantilla.objects.create(
            titulo="Encuesta Test", codigo="TEST_SEG", proceso="EVALUACION", activo=True
        )
        version = FormularioVersion.objects.create(
            plantilla=plantilla,
            numero_version=1,
            estado="PUBLICADA",
            fecha_creacion=ahora - timedelta(days=2),
            fecha_fin_vigencia=ahora - timedelta(minutes=10),
        )
        enlace_enc = EnlaceFormulario.objects.create(
            version=version,
            token=uuid.uuid4(),
            fecha_inicio=ahora - timedelta(days=2),
            activo=True,
        )
        url_enc = reverse("encuestas:responder", args=[enlace_enc.token])
        resp_enc = client.get(url_enc)
        self.assertEqual(resp_enc.status_code, 200)
        self.assertTemplateUsed(resp_enc, "encuestas/cerrado.html")

        # 3. Token manipulado / inexistente devuelve 404
        self.assertEqual(
            client.get(reverse("encuestas:responder", args=[uuid.uuid4()])).status_code,
            404,
        )

    # ------------------------------------------------------------------
    # CDE-388: Verificar que archivos privados no sean públicos
    # ------------------------------------------------------------------
    def test_cde388_archivos_privados_no_accesibles_publicamente(self):
        client = Client()
        pdf_dummy = SimpleUploadedFile(
            "documento_confidencial.pdf",
            b"%PDF-1.4\n%contenido confidencial",
            content_type="application/pdf",
        )
        archivo = guardar_archivo(pdf_dummy, autor=self.coordinador)

        # Descarga directa anónima redirige a login
        url_descarga = reverse("archivos:descargar", args=[archivo.pk])
        self.assertEqual(client.get(url_descarga).status_code, 302)

        # Usuario docente sin permisos sobre el archivo recibe 403
        client.force_login(self.docente_user_1)
        self.assertEqual(client.get(url_descarga).status_code, 403)

        # Recurso privado en repositorio no es accesible en ruta pública aunque se adivine el ID
        client.logout()
        recurso_privado = RecursoRepositorio.objects.create(
            titulo="Manual Interno Solo Coordinación",
            categoria="GUIAS",
            visibilidad="PRIVADO",
            estado="PUBLICADO",
            archivo=archivo,
            publicado_por_usuario=self.coordinador,
        )
        url_pub_descarga = reverse("archivos:descargar_recurso_publico", args=[recurso_privado.pk])
        self.assertEqual(client.get(url_pub_descarga).status_code, 404)

    # ------------------------------------------------------------------
    # CDE-389: Verificar que RUT / correos / teléfonos no aparezcan en público
    # ------------------------------------------------------------------
    def test_cde389_privacidad_datos_sensibles_en_portal_publico(self):
        comuna = Comuna.objects.create(
            nombre="Temuco",
            region="La Araucanía",
            lat_centro=-38.7359,
            lon_centro=-72.5904,
            activo=True,
        )
        socio = SocioComunitario.objects.create(
            nombre_organizacion="Junta Vecinos Sensible",
            rut="76543210-K",
            comuna=comuna,
            direccion_exacta="Calle Privada Secreta 999",
            estado_revision="APROBADO",
            es_provisional=False,
            activo=True,
            fecha_creacion=timezone.now(),
        )
        ContactoSocio.objects.create(
            socio=socio,
            nombre="Persona Contacto Privada",
            correo="contacto_secreto@ejemplo.cl",
            telefono="+56987654321",
            es_principal=True,
            activo=True,
        )
        ParticipacionSocio.objects.create(
            socio=socio,
            seccion=self.seccion_1,
            periodo=self.periodo,
            carrera=self.carrera,
            asignatura=self.asignatura,
            servicio_realizado="Asesoría contable comunitaria",
            origen="HISTORICO",
        )

        # Habilitar todos los bloques públicos
        config = ConfiguracionPortal.objects.first() or ConfiguracionPortal.objects.create()
        config.opciones_json = {
            "mapa": {"activo": True, "opciones": ["socios", "participaciones", "proyectos", "carreras", "anios"]},
            "cifras": {"activo": True},
            "catalogo": {"activo": True},
            "repositorio": {"activo": True},
            "noticias": {"activo": True},
        }
        config.save()

        client = Client()
        resp = client.get(reverse("core:inicio"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")

        # Ningún dato personal o identificatorio debe filtrarse al portal público
        self.assertNotIn("76543210-K", html)
        self.assertNotIn("contacto_secreto@ejemplo.cl", html)
        self.assertNotIn("+56987654321", html)
        self.assertNotIn("Calle Privada Secreta 999", html)
        self.assertNotIn("Junta Vecinos Sensible", html)
        self.assertNotIn("11111111-1", html)

    # ------------------------------------------------------------------
    # CDE-390: Revisar secretos en el repositorio
    # ------------------------------------------------------------------
    def test_cde390_sin_secretos_en_repositorio(self):
        base_dir = Path(settings.BASE_DIR)

        # 1. Verificar reglas críticas en .gitignore
        gitignore = (base_dir / ".gitignore").read_text(encoding="utf-8")
        for patron in (".env", "db.sqlite3", "private_uploads/", "firma_prueba*"):
            self.assertIn(patron, gitignore)

        # 2. Verificar que .env.example no contenga contraseñas reales ni keys de producción
        env_example = (base_dir / ".env.example").read_text(encoding="utf-8")
        self.assertNotIn("django-insecure-", env_example)
        self.assertIsNone(re.search(r"PASSWORD=(?!tu_contrasena)[A-Za-z0-9!@#$%^&*]{8,}", env_example))