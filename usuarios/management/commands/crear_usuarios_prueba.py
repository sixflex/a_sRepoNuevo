from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from academico.models import (
    Asignatura,
    Campus,
    Carrera,
    Docente,
    Facultad,
    PeriodoAcademico,
    Seccion,
    SeccionCarrera,
    SeccionDocente,
    Sede,
)


class Command(BaseCommand):
    help = "Crea usuarios y datos académicos de prueba"

    @transaction.atomic
    def handle(self, *args, **options):

        User = get_user_model()

        grupo_coordinador, _ = Group.objects.get_or_create(
            name="Coordinador"
        )

        grupo_docente, _ = Group.objects.get_or_create(
            name="Docente"
        )

        coordinador, _ = User.objects.get_or_create(
            username="coordinador"
        )
        coordinador.set_password("Coord1234")
        coordinador.is_active = True
        coordinador.save()
        coordinador.groups.set([grupo_coordinador])

        usuario_docente1, _ = User.objects.get_or_create(
            username="docente1"
        )
        usuario_docente1.set_password("Docente1234")
        usuario_docente1.is_active = True
        usuario_docente1.save()
        usuario_docente1.groups.set([grupo_docente])

        usuario_docente2, _ = User.objects.get_or_create(
            username="docente2"
        )
        usuario_docente2.set_password("Docente1234")
        usuario_docente2.is_active = True
        usuario_docente2.save()
        usuario_docente2.groups.set([grupo_docente])

        sede, _ = Sede.objects.get_or_create(
            nombre="Sede Santiago",
            defaults={
                "ciudad": "Santiago",
                "activo": True,
            },
        )

        campus, _ = Campus.objects.get_or_create(
            sede=sede,
            nombre="Campus Providencia",
            defaults={
                "activo": True,
            },
        )

        facultad, _ = Facultad.objects.get_or_create(
            codigo="FAING",
            defaults={
                "nombre": "Facultad de Ingeniería",
                "activo": True,
            },
        )

        carrera, _ = Carrera.objects.get_or_create(
            codigo="ICI",
            defaults={
                "nombre": "Ingeniería Civil Informática",
                "facultad": facultad,
                "activo": True,
            },
        )

        asignatura, _ = Asignatura.objects.get_or_create(
            codigo="AS001",
            defaults={
                "nombre": "Asignatura A+S de Prueba",
                "activo": True,
            },
        )

        asignatura.carreras.add(carrera)

        periodo, _ = PeriodoAcademico.objects.get_or_create(
            anio=2026,
            tipo="Segundo semestre",
            nombre="Primavera 2026",
            defaults={
                "estado": "Activo",
            },
        )

        docente1, _ = Docente.objects.update_or_create(
            rut="11111111-1",
            defaults={
                "usuario": usuario_docente1,
                "nombres": "Docente",
                "apellidos": "Uno",
                "correo_institucional": "docente1@uautonoma.cl",
                "activo": True,
            },
        )

        docente2, _ = Docente.objects.update_or_create(
            rut="22222222-2",
            defaults={
                "usuario": usuario_docente2,
                "nombres": "Docente",
                "apellidos": "Dos",
                "correo_institucional": "docente2@uautonoma.cl",
                "activo": True,
            },
        )

        seccion1, _ = Seccion.objects.get_or_create(
            periodo=periodo,
            nrc="10001",
            defaults={
                "campus": campus,
                "asignatura": asignatura,
                "seccion": "1",
                "jornada": "Diurna",
                "estado": "Activo",
            },
        )

        seccion2, _ = Seccion.objects.get_or_create(
            periodo=periodo,
            nrc="20001",
            defaults={
                "campus": campus,
                "asignatura": asignatura,
                "seccion": "2",
                "jornada": "Diurna",
                "estado": "Activo",
            },
        )

        SeccionDocente.objects.get_or_create(
            seccion=seccion1,
            docente=docente1,
        )

        SeccionDocente.objects.get_or_create(
            seccion=seccion2,
            docente=docente2,
        )

        SeccionCarrera.objects.get_or_create(
            seccion=seccion1,
            carrera=carrera,
        )

        SeccionCarrera.objects.get_or_create(
            seccion=seccion2,
            carrera=carrera,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Usuarios y datos académicos de prueba creados correctamente."
            )
        )