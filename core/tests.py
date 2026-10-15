from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from academico.models import (
    Asignatura,
    Campus,
    Docente,
    PeriodoAcademico,
    Seccion,
    SeccionDocente,
    Sede,
)


class PanelDocenteFiltroPeriodoTestCase(TestCase):

    def setUp(self):
        User = get_user_model()

        self.grupo_docente, _ = Group.objects.get_or_create(name="Docente")

        # Docente 1
        self.user_docente1 = User.objects.create_user(
            username="docente1",
            password="DocentePassword1",
        )
        self.user_docente1.groups.add(self.grupo_docente)

        self.docente1 = Docente.objects.create(
            usuario=self.user_docente1,
            rut="11111111-1",
            nombres="Docente",
            apellidos="Uno",
            correo_institucional="docente1@uautonoma.cl",
            activo=True,
        )

        # Docente 2
        self.user_docente2 = User.objects.create_user(
            username="docente2",
            password="DocentePassword2",
        )
        self.user_docente2.groups.add(self.grupo_docente)

        self.docente2 = Docente.objects.create(
            usuario=self.user_docente2,
            rut="22222222-2",
            nombres="Docente",
            apellidos="Dos",
            correo_institucional="docente2@uautonoma.cl",
            activo=True,
        )

        # Infraestructura básica
        self.sede = Sede.objects.create(nombre="Sede Central", activo=True)
        self.campus = Campus.objects.create(sede=self.sede, nombre="Campus Central", activo=True)
        self.asignatura1 = Asignatura.objects.create(codigo="ASIG1", nombre="Asignatura 1", activo=True)
        self.asignatura2 = Asignatura.objects.create(codigo="ASIG2", nombre="Asignatura 2", activo=True)

        # Períodos
        self.periodo_2026_1 = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Primer semestre",
            nombre="2026 - Primer Semestre",
            estado="Activo",
        )
        self.periodo_2026_2 = PeriodoAcademico.objects.create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="2026 - Segundo Semestre",
            estado="Activo",
        )
        self.periodo_2025_2 = PeriodoAcademico.objects.create(
            anio=2025,
            tipo="Segundo semestre",
            nombre="2025 - Segundo Semestre",
            estado="Cerrado",
        )

        # Secciones Docente 1 en 2026-1
        self.sec_d1_p1 = Seccion.objects.create(
            periodo=self.periodo_2026_1,
            campus=self.campus,
            asignatura=self.asignatura1,
            nrc="1001",
            seccion="01",
            estado="Activa",
        )
        SeccionDocente.objects.create(seccion=self.sec_d1_p1, docente=self.docente1)

        # Secciones Docente 1 en 2026-2
        self.sec_d1_p2 = Seccion.objects.create(
            periodo=self.periodo_2026_2,
            campus=self.campus,
            asignatura=self.asignatura2,
            nrc="2001",
            seccion="02",
            estado="Activa",
        )
        SeccionDocente.objects.create(seccion=self.sec_d1_p2, docente=self.docente1)

        # Sección Docente 2 en 2026-1 (para verificar aislamiento)
        self.sec_d2_p1 = Seccion.objects.create(
            periodo=self.periodo_2026_1,
            campus=self.campus,
            asignatura=self.asignatura1,
            nrc="9001",
            seccion="99",
            estado="Activa",
        )
        SeccionDocente.objects.create(seccion=self.sec_d2_p1, docente=self.docente2)

        self.url = reverse("core:docente")

    def test_acceso_no_autenticado_redirige(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_sin_filtro_muestra_todas_las_secciones_del_docente(self):
        self.client.force_login(self.user_docente1)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        secciones = response.context["secciones"]
        self.assertEqual(len(secciones), 2)
        self.assertIn(self.sec_d1_p1, secciones)
        self.assertIn(self.sec_d1_p2, secciones)
        self.assertNotIn(self.sec_d2_p1, secciones)
        self.assertEqual(response.context["periodo_id"], "")
        self.assertIsNone(response.context["periodo_seleccionado"])

    def test_filtro_por_periodo_muestra_solo_secciones_del_periodo_seleccionado(self):
        self.client.force_login(self.user_docente1)

        # Filtrar por período 2026-1
        response = self.client.get(self.url, {"periodo": self.periodo_2026_1.id})
        self.assertEqual(response.status_code, 200)

        secciones = response.context["secciones"]
        self.assertEqual(len(secciones), 1)
        self.assertIn(self.sec_d1_p1, secciones)
        self.assertNotIn(self.sec_d1_p2, secciones)
        self.assertNotIn(self.sec_d2_p1, secciones)
        self.assertEqual(response.context["periodo_id"], str(self.periodo_2026_1.id))
        self.assertEqual(response.context["periodo_seleccionado"], self.periodo_2026_1)

        # Verificar que el HTML contiene el option marcado como selected
        self.assertContains(
            response,
            f'value="{self.periodo_2026_1.id}" selected',
        )

        # Filtrar por período 2026-2
        response_p2 = self.client.get(self.url, {"periodo": self.periodo_2026_2.id})
        self.assertEqual(response_p2.status_code, 200)

        secciones_p2 = response_p2.context["secciones"]
        self.assertEqual(len(secciones_p2), 1)
        self.assertIn(self.sec_d1_p2, secciones_p2)
        self.assertNotIn(self.sec_d1_p1, secciones_p2)
        self.assertNotIn(self.sec_d2_p1, secciones_p2)

    def test_filtro_aisla_secciones_entre_docentes(self):
        # Ambos tienen secciones en 2026-1, pero Docente 1 no debe ver las del Docente 2
        self.client.force_login(self.user_docente1)
        response = self.client.get(self.url, {"periodo": self.periodo_2026_1.id})
        secciones = response.context["secciones"]
        self.assertNotIn(self.sec_d2_p1, secciones)

        # Docente 2 solo debe ver su propia sección en 2026-1
        self.client.force_login(self.user_docente2)
        response_d2 = self.client.get(self.url, {"periodo": self.periodo_2026_1.id})
        secciones_d2 = response_d2.context["secciones"]
        self.assertEqual(len(secciones_d2), 1)
        self.assertIn(self.sec_d2_p1, secciones_d2)
        self.assertNotIn(self.sec_d1_p1, secciones_d2)

    def test_periodo_sin_secciones_muestra_estado_vacio(self):
        self.client.force_login(self.user_docente1)

        # Docente 1 no tiene secciones en 2025-2
        response = self.client.get(self.url, {"periodo": self.periodo_2025_2.id})
        self.assertEqual(response.status_code, 200)

        secciones = response.context["secciones"]
        self.assertEqual(len(secciones), 0)
        self.assertContains(response, "No tienes secciones asignadas en este período")
        self.assertContains(response, self.periodo_2025_2.nombre)
        self.assertContains(response, "Ver todos los períodos")

    def test_periodo_invalido_se_maneja_correctamente(self):
        self.client.force_login(self.user_docente1)

        # Parámetro no numérico
        response = self.client.get(self.url, {"periodo": "invalido"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["secciones"]), 2)

        # Parámetro numérico que no existe
        response_inexistente = self.client.get(self.url, {"periodo": "999999"})
        self.assertEqual(response_inexistente.status_code, 200)
        self.assertEqual(len(response_inexistente.context["secciones"]), 0)


class PanelDocentePendientesRutaTestCase(TestCase):

    def setUp(self):
        User = get_user_model()
        self.grupo_docente, _ = Group.objects.get_or_create(name="Docente")

        self.user_docente = User.objects.create_user(
            username="docente_ruta",
            password="DocentePassword123",
        )
        self.user_docente.groups.add(self.grupo_docente)

        self.docente = Docente.objects.create(
            usuario=self.user_docente,
            rut="33333333-3",
            nombres="Docente",
            apellidos="Ruta",
            correo_institucional="docenteruta@uautonoma.cl",
            activo=True,
        )

        self.sede = Sede.objects.create(nombre="Sede Ruta", activo=True)
        self.campus = Campus.objects.create(sede=self.sede, nombre="Campus Ruta", activo=True)
        self.asignatura = Asignatura.objects.create(codigo="RUT01", nombre="Asignatura Ruta", activo=True)
        self.periodo = PeriodoAcademico.objects.create(
            anio=2026, tipo="Primer semestre", nombre="2026 - 1", estado="Activo"
        )

        self.seccion = Seccion.objects.create(
            periodo=self.periodo,
            campus=self.campus,
            asignatura=self.asignatura,
            nrc="3001",
            seccion="03",
            estado="Activa",
        )
        SeccionDocente.objects.create(seccion=self.seccion, docente=self.docente)

        self.url = reverse("core:docente")

    @patch("core.views.obtener_recordatorios_ruta")
    def test_lista_pendientes_seccion(self, mock_recordatorios):
        """1. Que se listen los pendientes de la sección."""
        mock_recordatorios.return_value = {
            self.seccion.id: {
                "pendientes": ["Configurar syllabus", "Aprobar hitos"],
                "mostrar_invitacion": False
            }
        }
        self.client.force_login(self.user_docente)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        seccion_context = response.context["secciones"][0]
        self.assertIsNotNone(seccion_context.recordatorio_ruta)
        self.assertIn("Configurar syllabus", seccion_context.recordatorio_ruta["pendientes"])

    @patch("core.views.obtener_recordatorios_ruta")
    def test_actividad_completada_no_aparece(self, mock_recordatorios):
        """2. Que una actividad completada no aparezca."""
        mock_recordatorios.return_value = {
            self.seccion.id: {
                "pendientes": ["Otra actividad"],
                "mostrar_invitacion": False
            }
        }
        self.client.force_login(self.user_docente)
        response = self.client.get(self.url)
        
        seccion_context = response.context["secciones"][0]
        self.assertNotIn("Actividad completada", seccion_context.recordatorio_ruta["pendientes"])

    @patch("core.views.obtener_recordatorios_ruta")
    def test_ruta_completada_no_muestra_recordatorio(self, mock_recordatorios):
        """3. Que una Ruta completada no muestre recordatorio."""
        mock_recordatorios.return_value = {self.seccion.id: None}
        self.client.force_login(self.user_docente)
        response = self.client.get(self.url)
        
        seccion_context = response.context["secciones"][0]
        self.assertIsNone(seccion_context.recordatorio_ruta)

    @patch("core.views.obtener_recordatorios_ruta")
    def test_seccion_sin_ruta_no_muestra_recordatorio(self, mock_recordatorios):
        """4. Que una sección sin Ruta no muestre recordatorio."""
        mock_recordatorios.return_value = {} 
        self.client.force_login(self.user_docente)
        response = self.client.get(self.url)
        
        seccion_context = response.context["secciones"][0]
        self.assertIsNone(getattr(seccion_context, 'recordatorio_ruta', None))

    @patch("core.views.obtener_recordatorios_ruta")
    def test_actividad_cierre_sin_invitaciones_muestra_recordatorio_invitar(self, mock_recordatorios):
        """5. Que haya actividad de cierre sin invitaciones muestre el recordatorio de invitar."""
        mock_recordatorios.return_value = {
            self.seccion.id: {
                "pendientes": [],
                "mostrar_invitacion": True,
                "socios": [] 
            }
        }
        self.client.force_login(self.user_docente)
        response = self.client.get(self.url)
        
        seccion_context = response.context["secciones"][0]
        self.assertTrue(seccion_context.recordatorio_ruta["mostrar_invitacion"])
        self.assertEqual(len(seccion_context.recordatorio_ruta["socios"]), 0)

    @patch("core.views.obtener_recordatorios_ruta")
    def test_invitacion_registrada_muestra_socio(self, mock_recordatorios):
        """6. Que una invitación registrada muestre al socio."""
        mock_recordatorios.return_value = {
            self.seccion.id: {
                "pendientes": [],
                "mostrar_invitacion": True,
                "socios": ["Socio Comunitario A"]
            }
        }
        self.client.force_login(self.user_docente)
        response = self.client.get(self.url)
        
        seccion_context = response.context["secciones"][0]
        self.assertIn("Socio Comunitario A", seccion_context.recordatorio_ruta["socios"])

    @patch("core.views.obtener_recordatorios_ruta")
    def test_sin_actividad_cierre_no_aparece_invitacion(self, mock_recordatorios):
        """7. Que sin actividad de cierre no aparezca la invitación."""
        mock_recordatorios.return_value = {
            self.seccion.id: {
                "pendientes": ["Actividad 1"],
                "mostrar_invitacion": False 
            }
        }
        self.client.force_login(self.user_docente)
        response = self.client.get(self.url)
        
        seccion_context = response.context["secciones"][0]
        self.assertFalse(seccion_context.recordatorio_ruta["mostrar_invitacion"])