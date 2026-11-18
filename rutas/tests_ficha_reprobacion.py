from django.test import SimpleTestCase

from rutas.ficha import con_porcentaje_reprobacion


class PorcentajeReprobacionTests(SimpleTestCase):
    def test_se_calcula_despues_de_reprobados(self):
        filas = [
            ("Cantidad total de estudiantes (Si tiene más de 1 sección a su cargo, súmelas)", "40"),
            ("Cantidad de reprobados (Si tienen más de 1 sección, súmelas)", "3"),
        ]
        salida = con_porcentaje_reprobacion(filas)
        self.assertEqual(salida[2], ("Porcentaje de aprobación (calculado)", "92,5 %"))
        self.assertEqual(salida[3], ("Porcentaje de reprobación (calculado)", "7,5 %"))

    def test_sin_estudiantes_no_agrega_nada(self):
        filas = [("Cantidad de reprobados (Si tienen más de 1 sección, súmelas)", "3")]
        self.assertEqual(con_porcentaje_reprobacion(filas), filas)
