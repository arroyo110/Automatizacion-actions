# Sistema de Pruebas Automatizadas

Este proyecto utiliza GitHub Actions para automatizar las pruebas de la API de Django.

## Configuración Local

### Instalar dependencias de pruebas
```bash
pip install -r requirements.txt
```

### Ejecutar pruebas localmente
```bash
# Ejecutar todas las pruebas
python -m pytest

# Ejecutar pruebas de una app específica
python -m pytest api/usuarios/

# Ejecutar un archivo de prueba específico
python -m pytest api/usuarios/test_usuarios.py

# Ejecutar con más detalles
python -m pytest -v
```

## GitHub Actions

El workflow se ejecuta automáticamente en:
- Push a la rama `master`
- Pull requests a la rama `master`

### Configuración del Workflow

El archivo `.github/workflows/test-api.yml` está configurado para:

1. **Servicios**: MySQL 8.0 como base de datos de prueba
2. **Python**: Versión 3.10
3. **Dependencias**: Instalación automática desde `requirements.txt`
4. **Base de datos**: Configuración automática de permisos y bases de datos de prueba
5. **Pruebas**: Ejecución automática de pytest

### Variables de Entorno del Workflow

- `DJANGO_SETTINGS_MODULE`: winespa.settings
- `DB_NAME`: winespaapi
- `DB_USER`: wine
- `DB_PASSWORD`: tech
- `DB_HOST`: 127.0.0.1
- `DB_PORT`: 3306

## Estructura de Archivos

```
.github/
└── workflows/
    └── test-api.yml          # Workflow de GitHub Actions

pytest.ini                   # Configuración de pytest
requirements.txt             # Dependencias incluyendo pytest
TESTING.md                   # Esta documentación
```

## Configuración de pytest

El archivo `pytest.ini` está configurado para:
- Usar Django como framework de pruebas
- Buscar archivos de prueba en la carpeta `api/`
- Reutilizar la base de datos entre pruebas
- Ignorar migraciones durante las pruebas
- Suprimir advertencias de deprecación

## Notas Importantes

- Las pruebas se ejecutan en un entorno Ubuntu con MySQL 8.0
- Se crea automáticamente una base de datos de prueba `test_winespaapi`
- El usuario de base de datos `wine` tiene todos los permisos necesarios
- Las pruebas se ejecutan con el archivo `api/usuarios/test_usuarios.py` por defecto
