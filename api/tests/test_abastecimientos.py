from django.test import TestCase
from django.core.exceptions import ValidationError
from api.abastecimientos.models import Abastecimiento
from api.manicuristas.models import Manicurista
from datetime import date


class AbastecimientoTestCase(TestCase):

    def setUp(self):
        # Crear instancia de Manicurista para relacionar
        self.manicurista = Manicurista.objects.create(
            # Agrega aquí los campos obligatorios que defina tu modelo Manicurista
            nombre="Manu Test"
        )
        # Datos válidos para Abastecimiento
        self.data_valida = {
            'fecha': date.today(),
            'cantidad': 5,
            'manicurista': self.manicurista,
        }

    def test_crear_abastecimiento_valido(self):
        abastecimiento = Abastecimiento(**self.data_valida)
        try:
            abastecimiento.full_clean()
        except ValidationError:
            self.fail("full_clean() lanzó ValidationError con datos válidos")

    def test_cantidad_negativa_no_valida(self):
        datos = self.data_valida.copy()
        datos['cantidad'] = -10  # cantidad negativa inválida
        abastecimiento = Abastecimiento(**datos)
        with self.assertRaises(ValidationError):
            abastecimiento.full_clean()

    def test_str_retorna_str_esperado(self):
        abastecimiento = Abastecimiento.objects.create(**self.data_valida)
        esperado = f"Abastecimiento {abastecimiento.id} - {self.manicurista} ({abastecimiento.fecha})"
        self.assertEqual(str(abastecimiento), esperado)
