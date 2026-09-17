def es_coordinador(user):
    return (
        user.is_authenticated
        and user.groups.filter(name="Coordinador").exists()
    )


def es_docente(user):
    return (
        user.is_authenticated
        and user.groups.filter(name="Docente").exists()
    )