from django.test import TestCase
from django.core.exceptions import ValidationError
from api.insumos.models import Insumo
from api.categoriainsumos.models import CategoriaInsumo


class InsumoTestCase(TestCase):

    def setUp(self):
        # Crear una categoría válida para asociar al insumo
        self.categoria = CategoriaInsumo.objects.create(
            nombre="Categoría de prueba",
            estado="activo"
        )
        # Datos válidos para un Insumo
        self.data_valida = {
            'nombre': 'Insumo Test',
            'cantidad': 10,
            'estado': 'activo',
            'categoria_insumo': self.categoria,
        }

    def test_crear_insumo_valido(self):
        insumo = Insumo(**self.data_valida)
        try:
            insumo.full_clean()
        except ValidationError:
            self.fail("full_clean() lanzó ValidationError con datos válidos")

    def test_cantidad_negativa_no_valida(self):
        datos = self.data_valida.copy()
        datos['cantidad'] = -5  # negativo no permitido en PositiveIntegerField
        insumo = Insumo(**datos)
        with self.assertRaises(ValidationError):
            insumo.full_clean()

    def test_str_retorna_nombre(self):
        insumo = Insumo(**self.data_valida)
        self.assertEqual(str(insumo), self.data_valida['nombre'])
