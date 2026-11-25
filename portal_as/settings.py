from pathlib import Path
import os
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv()


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-key')


DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'


ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv(
    "DJANGO_SECURE_SSL_REDIRECT",
    "False" if DEBUG else "True",
).lower() == "true"

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_HSTS_SECONDS = 0 if DEBUG else int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"




INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'core',
    'usuarios',
    'proyectos',
    'socios',
    'encuestas',
    'reportes',
    'academico',
    'campus',
    'planificacion',
    "rutas",
    "archivos",
    "cartas",
    "comunicaciones",
    "publico",
    "auditoria",
    "historicos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "portal_as.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / 'templates'],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.menu_lateral",
            ],
        },
    },
]

WSGI_APPLICATION = "portal_as.wsgi.application"





if os.getenv('DB_NAME') and os.getenv('DB_USER') and os.getenv('DB_PASSWORD'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
         
        }
    }





AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]





LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Santiago'

USE_I18N = True

USE_TZ = True





STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'




DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = 'usuarios.Usuario'

LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "usuarios:login"



PRIVATE_STORAGE_BACKEND = os.getenv(
    "PRIVATE_STORAGE_BACKEND",
    "archivos.storage.PrivateFileSystemStorage",
)

PRIVATE_STORAGE_ROOT = Path(
    os.getenv(
        "PRIVATE_STORAGE_ROOT",
        str(BASE_DIR / "private_uploads"),
    )
)

if not PRIVATE_STORAGE_ROOT.is_absolute():
    PRIVATE_STORAGE_ROOT = BASE_DIR / PRIVATE_STORAGE_ROOT

PRIVATE_STORAGE_MAX_FILE_SIZE_MB = int(
    os.getenv("PRIVATE_STORAGE_MAX_FILE_SIZE_MB", "20")
)



REPOSITORIO_MAX_FILE_SIZE_MB = int(
    os.getenv("REPOSITORIO_MAX_FILE_SIZE_MB", "50")
)

PRIVATE_STORAGE_MAX_FILES_PER_ACTIVITY = int(
    os.getenv("PRIVATE_STORAGE_MAX_FILES_PER_ACTIVITY", "10")
)

private_storage_options = {}
if PRIVATE_STORAGE_BACKEND == "archivos.storage.PrivateFileSystemStorage":
    private_storage_options["location"] = str(PRIVATE_STORAGE_ROOT)

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "private": {
        "BACKEND": PRIVATE_STORAGE_BACKEND,
        "OPTIONS": private_storage_options,
    },
}

PRIVATE_STORAGE_ALLOWED_EXTENSIONS = os.getenv(
    "PRIVATE_STORAGE_ALLOWED_EXTENSIONS",
    "pdf,doc,docx,xls,xlsx,jpg,jpeg,png",
).lower().split(",")

PRIVATE_STORAGE_RETENTION_YEARS = int(os.getenv("PRIVATE_STORAGE_RETENTION_YEARS", "5"))




CARTA_FIRMA_PRUEBA_PATH = os.getenv("CARTA_FIRMA_PRUEBA_PATH", "")





CARTA_PLANTILLA_PATH = os.getenv("CARTA_PLANTILLA_PATH", "")




ENTRA_MODO = os.getenv("ENTRA_MODO", "")
ENTRA_TENANT_ID = os.getenv("ENTRA_TENANT_ID", "")
ENTRA_CLIENT_ID = os.getenv("ENTRA_CLIENT_ID", "")
ENTRA_CLIENT_SECRET = os.getenv("ENTRA_CLIENT_SECRET", "")
ENTRA_REDIRECT_URI = os.getenv("ENTRA_REDIRECT_URI", "")

COORDINADORES = os.getenv("COORDINADORES", "")





EMAIL_BACKEND_RESPALDO = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_BACKEND = "comunicaciones.backend.CorreoConfigurableBackend"

CORREO_CLAVE_CIFRADO = os.getenv("CORREO_CLAVE_CIFRADO", "")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.office365.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@portal-as.cl")