# Proyecto Backend Django - WineSpa

## Descripción

Este proyecto es el backend para realizar test a Insumos, Categoria Insumos, Proveedores, Clientes, Abastecimientos.

## Cómo desplegar el proyecto

1. Clona este repositorio

git clone https://github.com/arroyo110/Prueboso.git

cd Prueboso/Backend


2. Instala las dependencias

pip install -r requirements.txt


3. Configura las variables de entorno necesarias (ejemplo `.env`) si usa alguna configuración extra.

4. Aplica migraciones para crear la base de datos

python manage.py makemigrations

python manage.py migrate

## Cómo ejecutar las pruebas unitarias

1. python manage.py test api.tests.test_clientes

2. python manage.py test api.tests.test_abastecimientos

3. python manage.py test api.tests.test_insumos

4. python manage.py test api.tests.test_categoriainsumos

5. python manage.py test api.tests.test_proveedor
