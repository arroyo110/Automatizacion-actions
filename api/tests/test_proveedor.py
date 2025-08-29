import unittest
from django.core.exceptions import ValidationError
from api.proveedores.models import Proveedor  # Ajusta 'mi_app' por el nombre real de tu app

class ProveedorTestCase(unittest.TestCase):

    def setUp(self):
        # Datos válidos para un Proveedor
        self.data_valida = {
            'tipo_persona': 'natural',
            'nombre_empresa': 'Empresa XYZ',
            'nit': '1234567890',
            'nombre': 'Juan Perez',
            'direccion': 'Calle Falsa 123',
            'correo_electronico': 'juan@example.com',
            'celular': '+12345678901',
            'estado': 'activo',
        }

    def test_crear_proveedor_valido(self):
        proveedor = Proveedor(**self.data_valida)
        try:
            # full_clean valida los campos, sin guardar en DB
            proveedor.full_clean()
        except ValidationError:
            self.fail("full_clean() lanzó ValidationError con datos válidos")

    def test_celular_invalido(self):
        datos = self.data_valida.copy()
        datos['celular'] = '123456'  # formato celular inválido
        proveedor = Proveedor(**datos)
        with self.assertRaises(ValidationError):
            proveedor.full_clean()

    def test_str_retorna_nombre_empresa_y_nit(self):
        proveedor = Proveedor(**self.data_valida)
        esperado = f"{self.data_valida['nombre_empresa']} ({self.data_valida['nit']})"
        self.assertEqual(str(proveedor), esperado)


# Paso 5: Bloque para ejecutar pruebas desde la línea de comandos
if __name__ == '__main__':
    unittest.main()
