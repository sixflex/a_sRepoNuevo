# Procedimiento de Restauración y Recuperación (Disaster Recovery)
**Proyecto:** Portal Académico A+S  
**Responsable QA:** Sofía Díaz  
**Fecha de Validación:** 10 de noviembre de 2026  

El presente documento establece el protocolo técnico para restaurar el entorno completo del Portal A+S (Base de datos y almacenamiento físico) en un ambiente piloto o de contingencia.

## 1. Requisitos Previos
* Motor de base de datos PostgreSQL en ejecución.
* Haber creado una base de datos de destino completamente vacía (sin tablas ni migraciones previas).
* Tener detenido el servidor web de Django (`python manage.py runserver` apagado) para evitar bloqueos por conexiones activas.

## 2. Fase 1: Restauración de Base de Datos
Se debe utilizar el respaldo generado en formato custom (`.dump`). 
Ejecutar el siguiente comando desde la terminal. Se utiliza el flag `-1` (single transaction) como medida de seguridad para garantizar que, si ocurre un error, los cambios se reviertan y no quede una base de datos corrupta a medias:

```bash
# Crear base de datos vacía (si no existe)
createdb -U postgres bd_portal_as_contingencia

# Inyectar el respaldo en una sola transacción
pg_restore -U postgres -h localhost -d bd_portal_as_contingencia -1 respaldo_portal_as.dump

## Nota para el Equipo de Desarrollo (Entornos Locales)
Debido a que cada integrante mantiene su propia base de datos local, los comandos descritos en este manual y en el script `respaldar.bat` utilizan `postgres` y `portal_as` como valores por defecto. 
* **Para respaldar:** Antes de ejecutar `respaldar.bat`, ábrelo con un editor de texto y ajusta las variables `DB_USER` y `DB_NAME` según las credenciales de tu archivo `.env`.
* **Para restaurar:** Al ejecutar `pg_restore` o `createdb`, recuerda reemplazar `-U postgres` y `-d bd_portal_as_contingencia` por tu propio usuario local y el nombre que desees darle a tu base de datos de prueba.