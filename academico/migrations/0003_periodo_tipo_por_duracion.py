"""
RF-ACA-01: PeriodoAcademico.tipo guarda la duración (Anual, Semestral,
Trimestral, Bimestral) y la temporada va en el nombre ("Primavera 2026").

Solo cambia datos: "Primer semestre" y "Segundo semestre" pasan a
"Semestral". Para no perder en qué semestre se sitúa, si el nombre no lo
dice se le agrega: "Primavera 2026" pasa a "Primavera 2026 (2º semestre)".
Si ya existe un período Semestral con el mismo año y nombre
(restricción unique_periodo_academico), el registro conserva su valor
antiguo, que el formulario sigue mostrando. Hacia atrás no hace nada: no
se puede saber qué semestre era cada uno.
"""

from django.db import migrations

TIPOS_ANTIGUOS = ["Primer semestre", "Segundo semestre"]
SEMESTRAL = "Semestral"
ORDINAL_SEMESTRE = {
    "Primer semestre": "1er semestre",
    "Segundo semestre": "2º semestre",
}
LARGO_NOMBRE = 80


def nombre_con_semestre(nombre, tipo_antiguo):
    if "semestre" in nombre.lower():
        return nombre

    con_semestre = f"{nombre} ({ORDINAL_SEMESTRE[tipo_antiguo]})"
    return con_semestre if len(con_semestre) <= LARGO_NOMBRE else nombre


def pasar_a_semestral(apps, schema_editor):
    PeriodoAcademico = apps.get_model("academico", "PeriodoAcademico")

    for periodo in PeriodoAcademico.objects.filter(tipo__in=TIPOS_ANTIGUOS):
        ocupado = (
            PeriodoAcademico.objects
            .filter(anio=periodo.anio, tipo=SEMESTRAL, nombre=periodo.nombre)
            .exists()
        )

        if not ocupado:
            periodo.nombre = nombre_con_semestre(periodo.nombre, periodo.tipo)
            periodo.tipo = SEMESTRAL
            periodo.save(update_fields=["tipo", "nombre"])


class Migration(migrations.Migration):

    dependencies = [
        ("academico", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(pasar_a_semestral, migrations.RunPython.noop),
    ]
