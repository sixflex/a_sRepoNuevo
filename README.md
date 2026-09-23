# Portal Integrado A+S

Proyecto web desarrollado en Django para la gestión del Portal Integrado de Aprendizaje + Servicio.

## Estructura inicial de aplicaciones

- `core`: contiene la página de inicio, páginas públicas y elementos comunes del sistema.
- `usuarios`: gestiona autenticación, roles y funcionalidades asociadas a Coordinación y Docentes.
- `proyectos`: gestiona proyectos A+S, secciones, seguimiento y evidencias.
- `socios`: gestiona la información y funcionalidades relacionadas con los socios comunitarios.
- `encuestas`: contiene los formularios internos y el registro de sus resultados.
- `reportes`: contiene indicadores, reportes y consultas de información del sistema.

## Requisitos

- Anaconda o Miniconda.
- Python 3.11.
- PostgreSQL 17.
- Django 5.2.4.


### 1. Crear y activar entorno

conda create -n portal_as python=3.11
conda activate portal_as
pip install -r requirements.txt

### Las principales dependencias utilizadas son:

- Django 5.2.4
- psycopg2-binary 2.9.10
- python-dotenv

## Configurar variables de entorno y Generar la clave de Django

Crear un archivo llamado:
.env

en la misma carpeta donde está `manage.py`.
Tomar como referencia el archivo:
.env.example

El archivo `.env` debe tener:

DB_NAME=portal_as
DB_USER=postgres
DB_PASSWORD=TU_CONTRASEÑA
DB_HOST=localhost
DB_PORT=TU_PUERTO

DJANGO_DEBUG=True
DJANGO_SECRET_KEY=TU_CLAVE_SECRETA
Para generar esa clave secreta se debe ejecutar este comando:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
y el resultado que aparezca en la consola se pone aqui DJANGO_SECRET_KEY=

Cada integrante debe utilizar sus propias credenciales de PostgreSQL.
El archivo `.env` no debe subirse a Git.

## Ejecutar migraciones

Primero verificar que el proyecto esté correctamente configurado:
python manage.py check 
Y debe aparecer asi para seguir:
System check identified no issues (0 silenced).

Luego ejecutar:
python manage.py migrate

Si se realizan cambios en los modelos:
python manage.py makemigrations
python manage.py migrate

## Ejecutar el proyecto

Levantar el servidor:
python manage.py runserver

Para detener el servidor:
Ctrl + C

### Información importante

- No crear otro proyecto Django independiente.
- Todos deben trabajar sobre esta misma estructura.
- No subir `.env` al repositorio.
- No escribir contraseñas directamente en `settings.py`.
- Antes de comenzar a trabajar, activar siempre:
conda activate portal_as

- Si se agregan nuevas dependencias, actualizar `requirements.txt`.
- Cuando esté disponible el repositorio oficial, el trabajo se realizará utilizando las ramas `main`, `develop` y `feature`.

### Cada integrante trabaja en su rama personal. Cuando termina su tarea, hace un Pull Request de su rama hacia develop. Ahí se integran todos los cambios del sprint y ustedes prueban que el proyecto funcione completo.
### Cuando ya terminó el sprint y develop está estable, recién hacen un Pull Request de develop hacia main.
### Entonces:
### rama personal = trabajo de cada integrante
### develop = unión de todo el trabajo del sprint
#### main = versión estable/final 
