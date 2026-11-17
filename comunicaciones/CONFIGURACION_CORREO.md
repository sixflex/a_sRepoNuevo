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
python manage.py probar_correo --destinatario correo@uautonoma.cl```

---

## 3. Cuenta elegida desde el portal (Configuración → Correo de envío)
El Coordinador puede elegir desde qué cuenta salen los correos sin tocar el servidor
(tabla `ConfiguracionCorreo`, una sola fila). Todos los envíos pasan por
`comunicaciones/backend.py` (`EMAIL_BACKEND`):

* Cuenta activa en el portal → se envía con esa cuenta y ese remitente.
* Sin cuenta activa, o si su clave no se puede leer → se usa la cuenta del servidor
  (las variables de arriba; `EMAIL_BACKEND` del `.env` pasa a ser `EMAIL_BACKEND_RESPALDO`).
* Antes de activar una cuenta se prueba la conexión; si falla, no se guarda nada.
* La clave de aplicación se guarda cifrada (Fernet). La llave es `CORREO_CLAVE_CIFRADO`
  o, si no existe, `SECRET_KEY`. Si esa llave cambia, basta con volver a escribir la clave.
* Gmail: usar una contraseña de aplicación. Microsoft 365: DTI debe tener habilitado
  "SMTP AUTH" para esa cuenta.
* Cada cambio queda en auditoría (sin la clave).
