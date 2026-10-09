<<<<<<< HEAD
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

## Variables de Entorno (.env) para servicio transversal de comunicaciones

El proyecto requiere las siguientes variables en el archivo `.env`:

- `SECRET_KEY`: Clave secreta de Django.
- `DEBUG`: Modo depuración (`True` / `False`).
- `DB_NAME`: Nombre de la base de datos PostgreSQL (`portal_as`).
- `DB_USER`: Usuario de la base de datos (`postgres`).
- `DB_PASSWORD`: Contraseña del usuario de la base de datos.
- `DB_HOST`: Host de la base de datos (ej. `localhost`).
- `DB_PORT`: Puerto de conexión a PostgreSQL (`5432`).
- `DEFAULT_FROM_EMAIL`: Dirección de correo remitente por defecto para el servicio de comunicaciones.

## Servicio Transversal de Auditoría (módulo `auditoria`)

El sistema cuenta con un servicio común para registrar de forma uniforme las operaciones críticas y la trazabilidad de cambios en los diferentes módulos del Portal A+S.

### Características Principales
- **Entidad principal**: `AUDITORIA_CAMBIO` para el almacenamiento del historial de eventos.
- **Trazabilidad registrada**: Registra actor (usuario/responsable), tipo de operación, entidad afectada, resultado de la acción y marca de tiempo (fecha/hora).
- **Restricción de permisos**: Los registros de auditoría son de solo lectura y no pueden ser modificados por usuarios con rol Docente.

### Ejemplo de Uso en Servicios/Vistas
Para registrar un evento desde cualquier módulo, se utiliza el servicio común de auditoría:

### Ejemplo de Uso en Servicios/Vistas
Para registrar un evento desde cualquier módulo, se utiliza el servicio común de auditoría:

```python
from auditoria.services import AuditService

AuditService.registrar_evento(
    usuario=user,
    operacion="CREAR",  # O MODIFICAR, ELIMINAR, etc.
    entidad="SocioComunitario",
    resultado="EXITO",
    detalles={"campo_modificado": "nombre", "valor_nuevo": "Ejemplo"}
)
```


### Cada integrante trabaja en su rama personal. Cuando termina su tarea, hace un Pull Request de su rama hacia develop. Ahí se integran todos los cambios del sprint y ustedes prueban que el proyecto funcione completo.
### Cuando ya terminó el sprint y develop está estable, recién hacen un Pull Request de develop hacia main.
### Entonces:
### rama personal = trabajo de cada integrante
### develop = unión de todo el trabajo del sprint
#### main = versión estable/final
=======
# a_sRepoNuevo
>>>>>>> 36ebc7614817635fa65f5142c89265a611daa0d8
