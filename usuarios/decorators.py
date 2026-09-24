from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .permissions import es_coordinador, es_docente


def coordinador_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        # Superusuarios pueden acceder para administración/desarrollo    (temporal)
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        if not es_coordinador(request.user):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper

def docente_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        if not es_docente(request.user):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper