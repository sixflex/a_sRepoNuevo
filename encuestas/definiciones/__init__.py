"""
Formularios que el cliente usa hoy en Microsoft Forms (knowledge/Forms
preguntas.txt), listos para cargar con `python manage.py cargar_formularios`.
"""

from . import apoyo_fiscal, evaluaciones, ficha_emprendedores, registro_reflexion, resumen_implementacion

DEFINICIONES = [
    ficha_emprendedores.DEFINICION,
    resumen_implementacion.DEFINICION,
    evaluaciones.ESTUDIANTES,
    evaluaciones.SOCIOS_COMUNITARIOS,
    evaluaciones.DOCENTES,
    apoyo_fiscal.NUCLEO_APOYO_FISCAL,
    apoyo_fiscal.SATISFACCION_OPERACION_RENTA,
    registro_reflexion.DEFINICION,
]

POR_CODIGO = {definicion["codigo"]: definicion for definicion in DEFINICIONES}
