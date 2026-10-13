# El validador de RUT vive ahora en core.validators para que todo el portal
# use el mismo. Se reexporta aquí para no romper los imports existentes.
from core.validators import validar_rut_chileno  # noqa: F401
