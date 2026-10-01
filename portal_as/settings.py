from pathlib import Path
import os
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
print("BASE_DIR =", BASE_DIR)
print("ENV PATH =", BASE_DIR / ".env")

load_dotenv()


SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-dev-key')


DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'


ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


# Application definition

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
            ],
        },
    },
]

WSGI_APPLICATION = "portal_as.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

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


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Santiago'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = 'usuarios.Usuario'

LOGIN_URL = "usuarios:login"
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "usuarios:login"

# Private file storage
# SP3-T02: los binarios se almacenan fuera de PostgreSQL.
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
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
    "private": {
        "BACKEND": PRIVATE_STORAGE_BACKEND,
        "OPTIONS": private_storage_options,
    },
}

