from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import Periodo, Campus, Sede, Facultad, Carrera, Asignatura, Docente, Seccion

Usuario = get_user_model()

class PeriodoTests(TestCase):
    def setUp(self):
        # Crear grupo Coordinador y asignar al usuario de prueba
        self.grupo_coordinador = Group.objects.create(name="Coordinador")
        self.user = Usuario.objects.create_user(
            username="coordinador_test",
            password="Password123!"
        )
        self.user.groups.add(self.grupo_coordinador)
        self.client.login(username="coordinador_test", password="Password123!")

        # Registro base para pruebas
        self.periodo = Periodo.objects.create(anio=2026, tipo="Primer semestre")

    def test_crear_periodo_valido(self):
        response = self.client.post(reverse('periodo_create'), {
            'anio': '2026',
            'tipo': 'Segundo semestre'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Periodo.objects.filter(tipo='Segundo semestre').exists())

    def test_crear_periodo_invalido_anio_fuera_de_rango(self):
        response = self.client.post(reverse('periodo_create'), {
            'anio': '1990',
            'tipo': 'Primer semestre'
        })
        # Verifica que vuelva a renderizar la vista (status 200) y no redirija
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Periodo.objects.filter(anio=1990).exists())

    def test_editar_periodo(self):
        response = self.client.post(reverse('periodo_update', args=[self.periodo.pk]), {
            'anio': '2027',
            'tipo': 'Primer semestre'
        })
        self.assertEqual(response.status_code, 302)
        self.periodo.refresh_from_db()
        self.assertEqual(self.periodo.anio, 2027)

    def test_asociacion_periodo_seccion(self):
        campus = Campus.objects.create(nombre="Campus Central", direccion="Av. Principal")
        sede = Sede.objects.create(nombre="Sede A", ciudad="Santiago", campus=campus)
        facultad = Facultad.objects.create(nombre="Ingeniería")
        carrera = Carrera.objects.create(nombre="Informatica", facultad=facultad)
        asignatura = Asignatura.objects.create(nombre="Programación", carrera=carrera)
        docente = Docente.objects.create(nombre="Juan Perez", correo="juan@example.com")

        seccion = Seccion.objects.create(
            nrc="12345",
            asignatura=asignatura,
            docente=docente,
            periodo=self.periodo,
            sede=sede
        )
        self.assertEqual(seccion.periodo.anio, 2026)