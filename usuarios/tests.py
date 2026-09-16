from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from proyectos.models import Seccion


class PermisosTest(TestCase):

    def setUp(self):

        self.grupo_coordinador = Group.objects.create(
            name="Coordinador"
        )

        self.grupo_docente = Group.objects.create(
            name="Docente"
        )

        self.coordinador = User.objects.create_user(
            username="coordinador",
            password="test1234",
        )

        self.coordinador.groups.add(
            self.grupo_coordinador
        )

        self.docente1 = User.objects.create_user(
            username="docente1",
            password="test1234",
        )

        self.docente1.groups.add(
            self.grupo_docente
        )

        self.docente2 = User.objects.create_user(
            username="docente2",
            password="test1234",
        )

        self.docente2.groups.add(
            self.grupo_docente
        )

        self.seccion1 = Seccion.objects.create(
            nombre="Sección 1",
            nrc="111",
            docente=self.docente1,
        )

        self.seccion2 = Seccion.objects.create(
            nombre="Sección 2",
            nrc="222",
            docente=self.docente2,
        )


    def test_docente_no_accede_coordinacion(self):

        self.client.login(
            username="docente1",
            password="test1234",
        )

        response = self.client.get(
            reverse("core:coordinacion")
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_docente_accede_a_su_seccion(self):

        self.client.login(
            username="docente1",
            password="test1234",
        )

        response = self.client.get(
            reverse(
                "core:detalle_seccion",
                args=[self.seccion1.id],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )


    def test_docente_no_accede_a_seccion_ajena(self):

        self.client.login(
            username="docente1",
            password="test1234",
        )

        response = self.client.get(
            reverse(
                "core:detalle_seccion",
                args=[self.seccion2.id],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )


    def test_coordinador_accede_coordinacion(self):

        self.client.login(
            username="coordinador",
            password="test1234",
        )

        response = self.client.get(
            reverse("core:coordinacion")
        )

        self.assertEqual(
            response.status_code,
            200,
        )


    def test_usuario_anonimo_es_enviado_a_login(self):

        response = self.client.get(
            reverse("core:coordinacion")
        )

        self.assertEqual(
            response.status_code,
            302,
        )