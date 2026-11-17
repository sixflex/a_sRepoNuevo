"""
Deja a una persona como Coordinador A+S (respaldo para que el portal nunca
quede sin quién lo administre).

    python manage.py crear_coordinador jreino@uautonoma.cl
    python manage.py crear_coordinador jreino@uautonoma.cl --clave

Sin --clave, la persona entra con su cuenta Microsoft: la primera vez que
ingrese, el portal reconoce su correo y la deja como Coordinador.
Con --clave se le pide una contraseña y puede usar el "Acceso de respaldo"
de la pantalla de login aunque Microsoft no funcione.
"""

import getpass

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from usuarios import entra, services


class Command(BaseCommand):
    help = "Crea o actualiza un Coordinador A+S por su correo institucional."

    def add_arguments(self, parser):
        parser.add_argument("correo")
        parser.add_argument("--nombre", default="", help="Nombre (opcional).")
        parser.add_argument("--apellido", default="", help="Apellido (opcional).")
        parser.add_argument(
            "--clave", action="store_true",
            help="Pide una contraseña para el acceso de respaldo.",
        )

    def handle(self, *args, correo, nombre, apellido, clave, **opciones):
        correo = services.normalizar_correo(correo)
        try:
            validate_email(correo)
        except ValidationError as exc:
            raise CommandError(f"Correo no válido: {correo}") from exc
        if correo.rsplit("@", 1)[1] not in entra.dominios_permitidos():
            raise CommandError(f"Solo se aceptan cuentas {entra.texto_dominios()}.")

        usuario = services.usuario_por_correo(correo)
        creado = usuario is None
        if creado:
            usuario = get_user_model()(
                username=correo, email=correo, correo_institucional=correo,
                first_name=nombre, last_name=apellido,
            )
            usuario.set_unusable_password()
            usuario.save()

        if clave:
            primera = getpass.getpass("Contraseña de respaldo: ")
            if not primera or primera != getpass.getpass("Repite la contraseña: "):
                raise CommandError("Las contraseñas no coinciden o están vacías.")
            usuario.set_password(primera)
            usuario.save(update_fields=["password"])

        services.dar_rol_coordinador(usuario)

        self.stdout.write(self.style.SUCCESS(
            f"{'Creado' if creado else 'Actualizado'}: {correo} es Coordinador A+S."
            + (" Tiene contraseña de respaldo." if clave else " Entra con su cuenta Microsoft.")
        ))
