# Configuración del Servicio Transversal de Correo Institucional (SP6-T01 / CDE-326)

## 1. Módulos y Variables de Entorno (CDE-342, CDE-343, CDE-349)
El servicio utiliza `python-dotenv` para cargar credenciales dinámicas sin exponiendo información sensible en el repositorio de Git.

Variables de entorno requeridas en `.env`:
* `EMAIL_BACKEND`: `django.core.mail.backends.smtp.EmailBackend` (o `console.EmailBackend` para entorno de pruebas/piloto).
* `EMAIL_HOST`: Servidor SMTP institucional (ej. `smtp.office365.com`).
* `EMAIL_PORT`: Puerto TLS (ej. `587`).
* `EMAIL_USE_TLS`: `True`.
* `EMAIL_HOST_USER`: Cuenta autorizada de Coordinación A+S (`coordinacion.as@uautonoma.cl`).
* `EMAIL_HOST_PASSWORD`: Secreto/contraseña de aplicación.
* `DEFAULT_FROM_EMAIL`: `Coordinación A+S <coordinacion.as@uautonoma.cl>`.

---

## 2. Ejecución de Envíos de Prueba (CDE-344, CDE-345)
Para validar el envío de prueba en ambiente controlado, ejecutar desde la consola:

```bash
python manage.py probar_correo --destinatario correo@uautonoma.cl