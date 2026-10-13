"""
Validación y normalización de RUT chileno, compartida por todo el portal.

El RUT se guarda siempre sin puntos y con guion (ej. 12345678-5) para que
las búsquedas por RUT encuentren el mismo registro sin importar cómo se
escribió (RNF-DAT-01).
"""
import re
from itertools import cycle

from django.core.exceptions import ValidationError


def limpiar_rut(rut):
    """Deja solo dígitos y K (en mayúscula)."""
    return re.sub(r"[^0-9kK]", "", str(rut or "")).upper()


def normalizar_rut(rut):
    """
    Formato de almacenamiento "12345678-5", sin validar el dígito verificador.
    Sirve para comparar o buscar RUT escritos de distintas formas.
    """
    rut_limpio = limpiar_rut(rut)

    if len(rut_limpio) < 2:
        return rut_limpio

    return f"{rut_limpio[:-1]}-{rut_limpio[-1]}"


def validar_rut_chileno(rut_str):
    """
    Valida el dígito verificador (módulo 11) y devuelve el RUT normalizado.
    Acepta el RUT con o sin puntos y guion.
    """
    if not rut_str:
        raise ValidationError("El RUT es obligatorio.", code="rut_vacio")

    rut_limpio = limpiar_rut(rut_str)

    if len(rut_limpio) < 2:
        raise ValidationError("El RUT ingresado no es válido.", code="rut_invalido")

    cuerpo = rut_limpio[:-1]
    dv = rut_limpio[-1]

    if not cuerpo.isdigit():
        raise ValidationError("El cuerpo del RUT solo debe contener números.", code="rut_invalido")

    # Algoritmo estándar Módulo 11 (Chile)
    factores = cycle([2, 3, 4, 5, 6, 7])
    suma = sum(int(digito) * factor for digito, factor in zip(reversed(cuerpo), factores))
    resto = suma % 11
    dv_esperado = 11 - resto

    if dv_esperado == 11:
        dv_calculado = "0"
    elif dv_esperado == 10:
        dv_calculado = "K"
    else:
        dv_calculado = str(dv_esperado)

    if dv != dv_calculado:
        raise ValidationError("El dígito verificador del RUT es incorrecto.", code="rut_invalido")

    return f"{cuerpo}-{dv}"


def es_rut_valido(rut):
    """Versión booleana de validar_rut_chileno, para validaciones en bucle."""
    try:
        validar_rut_chileno(rut)
    except ValidationError:
        return False

    return True
