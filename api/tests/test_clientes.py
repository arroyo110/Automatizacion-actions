from django.test import TestCase
from django.core.exceptions import ValidationError
from api.clientes.models import Cliente
from api.usuarios.models import Usuario
from api.roles.models import Rol


class ClienteTestCase(TestCase):

    def setUp(self):
        # Crear rol 'cliente' o usar uno existente
        self.rol_cliente, _ = Rol.objects.get_or_create(
            nombre__iexact='cliente',
            defaults={'nombre': 'Cliente', 'estado': 'activo'}
        )
        # Crear usuario base para la relación en Cliente
        self.usuario_base = Usuario.objects.create(
            nombre="Usuario Prueba",
            tipo_documento="CC",
            documento="12345678",
            direccion="Calle Prueba 123",
            celular="+12345678901",
            correo_electronico="usuario@prueba.com",
            rol=self.rol_cliente,
            is_active=True,
            is_staff=False
        )
        # Datos válidos para cliente
        self.data_valida = {
            'tipo_documento': 'CC',
            'documento': '9876543210',
            'nombre': 'Cliente Test',
            'celular': '+12345678902',
            'correo_electronico': 'cliente@prueba.com',
            'direccion': 'Calle Cliente 45',
            'genero': 'M',
            'estado': True,
            'usuario': self.usuario_base,
        }

    def test_crear_cliente_valido(self):
        cliente = Cliente(**self.data_valida)
        try:
            cliente.full_clean()
        except ValidationError:
            self.fail("full_clean() lanzó ValidationError con datos válidos")

    def test_celular_invalido(self):
        datos = self.data_valida.copy()
        datos['celular'] = '12345'  # formato inválido
        cliente = Cliente(**datos)
        with self.assertRaises(ValidationError):
            cliente.full_clean()

    def test_str_retorna_nombre_y_documento(self):
        cliente = Cliente(**self.data_valida)
        esperado = f"{self.data_valida['nombre']} ({self.data_valida['documento']})"
        self.assertEqual(str(cliente), esperado)
