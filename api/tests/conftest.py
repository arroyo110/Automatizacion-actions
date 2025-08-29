import pytest
from django.conf import settings

# Configurar pytest-django para permitir acceso a la base de datos
pytest_plugins = ['pytest_django']

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Configurar la base de datos para las pruebas"""
    with django_db_blocker.unblock():
        pass

@pytest.fixture(scope='function')
def db_access_without_rollback_and_truncate(django_db_setup, django_db_blocker):
    """Permitir acceso a la base de datos sin rollback"""
    django_db_blocker.unblock()
    yield
    django_db_blocker.restore()
