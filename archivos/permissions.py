from usuarios.permissions import es_coordinador


def puede_descargar_archivo(user, archivo):
    if not user.is_authenticated:
        return False

    if user.is_superuser or es_coordinador(user):
        return True

    return archivo.cargado_por_usuario_id == user.id
