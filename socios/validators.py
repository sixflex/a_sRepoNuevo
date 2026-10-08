import re
from itertools import cycle
from django.core.exceptions import ValidationError


def validar_rut_chileno(rut_str):
    if not rut_str:
        raise ValidationError("El RUT es obligatorio.", code="rut_vacio")

    # Limpiar espacios, puntos y guiones
    rut_limpio = re.sub(r"[^0-9kK]", "", str(rut_str)).upper()

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