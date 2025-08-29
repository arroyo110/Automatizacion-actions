import unittest
from django.core.exceptions import ValidationError
from api.categoriainsumos.models import CategoriaInsumo  # Ajusta la ruta si es necesario


class CategoriaInsumoTestCase(unittest.TestCase):

    def setUp(self):
        # Datos válidos para una Categoría de Insumo
        self.data_valida = {
            'nombre': 'Insumo Test',
            'estado': 'activo',
        }

    def test_crear_categoria_valida(self):
        categoria = CategoriaInsumo(**self.data_valida)
        try:
            # full_clean valida los campos sin guardar en la DB
            categoria.full_clean()
        except ValidationError:
            self.fail("full_clean() lanzó ValidationError con datos válidos")

    def test_estado_invalido(self):
        datos = self.data_valida.copy()
        datos['estado'] = 'desconocido'  # Valor no permitido según choices
        categoria = CategoriaInsumo(**datos)
        with self.assertRaises(ValidationError):
            categoria.full_clean()

    def test_str_retorna_nombre(self):
        categoria = CategoriaInsumo(**self.data_valida)
        self.assertEqual(str(categoria), self.data_valida['nombre'])


if __name__ == '__main__':
    unittest.main()
