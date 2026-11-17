# Conectar el portal A+S con Microsoft (Entra ID)

Guía para TI de la Universidad Autónoma. El código ya está listo: solo hay que
registrar la aplicación y poner 4 valores en el servidor. No se toca código.

## Qué hace el portal con Microsoft

- Microsoft **solo confirma quién es la persona** (nombre, correo, id). El portal
  no lee correos, archivos ni la base de datos de la universidad.
- Permiso pedido: `User.Read` (perfil básico). Flujo OpenID Connect
  "authorization code" con PKCE, librería oficial `msal`.
- El **rol lo decide el portal** con sus propios datos:
  - Coordinador: correo en la variable `COORDINADORES` o ya marcado como Coordinador.
  - Docente: correo de un docente cargado en la planificación A+S.
  - Cualquier otra cuenta de la U: entra, pero ve un aviso "sin panel" (no ve datos internos).
- Solo se aceptan cuentas de los tenants configurados y de los dominios
  `@uautonoma.cl` y `@cloud.uautonoma.cl`.

Código: `usuarios/entra.py` (clase `ConectorEntraMicrosoft`) y
`usuarios/views.py` (`_ir_a_microsoft`, `entra_callback`).

## 1. Registrar la aplicación (Entra ID → App registrations → New registration)

| Campo | Valor |
|---|---|
| Nombre | Portal A+S |
| Tipos de cuenta | *Accounts in any organizational directory* (multi-tenant), porque la U tiene dos tenants: `uautonoma.cl` y `cloud.uautonoma.cl` |
| Redirect URI (Web) | `https://portal-as.onrender.com/usuarios/auth/callback/` |

Para pruebas locales se puede agregar también `http://localhost:8000/usuarios/auth/callback/`.

Luego:

1. **Certificates & secrets → New client secret**. Copiar el *Value* (se ve una sola vez).
2. **API permissions**: dejar `Microsoft Graph → User.Read` (delegado) y presionar
   **Grant admin consent** en cada tenant donde se use. Si no se da el
   consentimiento, la persona verá "La universidad debe aprobar esta aplicación".

Tenants de la universidad (públicos, sacados de `login.microsoftonline.com/<dominio>/v2.0/.well-known/openid-configuration`):

| Dominio | Tenant ID |
|---|---|
| uautonoma.cl | `5467f788-2de9-4c6c-bfb4-863594d809cf` |
| cloud.uautonoma.cl | `60dac1b9-6047-489a-a134-b070386cccf7` |

## 2. Variables en el servidor (Render → Environment)

```
ENTRA_MODO=microsoft
ENTRA_TENANT_ID=5467f788-2de9-4c6c-bfb4-863594d809cf,60dac1b9-6047-489a-a134-b070386cccf7
ENTRA_CLIENT_ID=<Application (client) ID>
ENTRA_CLIENT_SECRET=<Value del secreto>
COORDINADORES=correo.coordinador@uautonoma.cl
```

Opcionales: `ENTRA_REDIRECT_URI` (si la URL de vuelta no es la del mismo
dominio) y `ENTRA_DOMINIOS_PERMITIDOS` (por defecto `uautonoma.cl,cloud.uautonoma.cl`).

Con un solo tenant en `ENTRA_TENANT_ID` se usa ese directorio; con dos o más se
usa `organizations` y el portal revisa que el tenant de la cuenta sea uno de ellos.

## 3. Acceso de respaldo (el portal nunca queda sin entrada)

Si Microsoft falla, falta el consentimiento o vence el secreto, la pantalla de
login sigue teniendo **"Acceso de respaldo (usuario y contraseña)"**. Para dar
una clave de respaldo a un Coordinador:

```
python manage.py crear_coordinador correo@uautonoma.cl --clave
```

Sin `--clave`, el comando solo lo deja como Coordinador y entra con Microsoft.

Para volver atrás sin tocar código: `ENTRA_MODO=desactivado` (solo usuario y
contraseña) o `ENTRA_MODO=simulado` (pantalla de demostración, solo desarrollo).

## 4. Probar

1. Abrir `/usuarios/login/` → "Iniciar sesión con Microsoft".
2. Entrar con una cuenta de la U → debe volver al portal con sesión iniciada.
3. Si aparece un error, el mensaje dice qué falta (variable, consentimiento,
   tenant o dominio no aceptado) y ofrece el acceso de respaldo.

Pruebas automáticas: `python manage.py test usuarios.tests_microsoft`.

## 5. Mantención

- El secreto vence (6 a 24 meses según se cree). Antes de que venza, crear uno
  nuevo y cambiar `ENTRA_CLIENT_SECRET` en Render.
- Nunca subir el secreto al repositorio.
