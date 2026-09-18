from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from proyectos.models import Seccion

Usuario = get_user_model()

class Command(BaseCommand):

    help = "Crea usuarios y datos ficticios para probar permisos."


    def handle(self, *args, **options):

        coordinador_group, _ = Group.objects.get_or_create(
            name="Coordinador"
        )

        docente_group, _ = Group.objects.get_or_create(
            name="Docente"
        )

        coordinador, creado = Usuario.objects.get_or_create(
            username="coordinador"
        )

        coordinador.set_password("Coord1234!")
        coordinador.save()

        coordinador.groups.add(
            coordinador_group
        )

        docente1, _ = Usuario.objects.get_or_create(
            username="docente1"
        )

        docente1.set_password("Docente1234!")
        docente1.save()

        docente1.groups.add(
            docente_group
        )

        docente2, _ = Usuario.objects.get_or_create(
            username="docente2"
        )

        docente2.set_password("Docente1234!")
        docente2.save()

        docente2.groups.add(
            docente_group
        )

        Seccion.objects.get_or_create(
            nrc="10001",
            defaults={
                "nombre": "Sección Docente 1",
                "docente": docente1,
            },
        )

        Seccion.objects.get_or_create(
            nrc="20001",
            defaults={
                "nombre": "Sección Docente 2",
                "docente": docente2,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Usuarios y secciones de prueba creados."
            )
        )