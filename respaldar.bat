@echo off
REM --- CONFIGURACION LOCAL ---
set DB_USER=postgres
set DB_NAME=portal_as

REM Ruta a PostgreSQL (Cambia el "16" por tu version si tienes la 14, 15, etc.)
set PG_PATH="C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
REM ---------------------------

echo Iniciando respaldo del Portal A+S...

REM 1. Respaldo de la base de datos PostgreSQL
echo Respaldando la base de datos...
%PG_PATH% -U %DB_USER% -h localhost -d %DB_NAME% -F c -f respaldo_portal_as.dump

REM 2. Asegurar que exista la carpeta media y respaldar
echo Verificando carpeta de archivos...
if not exist media mkdir media

echo Respaldando archivos multimedia...
tar -a -c -f respaldo_media.zip media

echo Respaldo completado!
pause