

from pathlib import Path
import os
from urllib.parse import quote_plus
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-for-dev')


def get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = get_bool_env('DEBUG', False)

allowed_hosts = os.getenv('ALLOWED_HOSTS', '')
hosts = [h.strip() for h in allowed_hosts.split(',') if h.strip()] if allowed_hosts else []

for host in [
    os.getenv('RAILWAY_PUBLIC_DOMAIN'),
    os.getenv('RAILWAY_PRIVATE_DOMAIN'),
]:
    if host:
        hosts.append(host)

LOCAL_ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '192.168.88.252',
    '192.168.88.244',
    'hivplus.local',
    'diversehearts.local',
]

ALLOWED_HOSTS = hosts or LOCAL_ALLOWED_HOSTS

APP_VARIANT_DOMAINS = {
    'hiv_plus': [
        host.strip()
        for host in os.getenv('HIV_PLUS_DOMAIN', '').split(',')
        if host.strip()
    ],
    'general': [
        host.strip()
        for host in os.getenv('GENERAL_DOMAIN', '').split(',')
        if host.strip()
    ],
}

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://192.168.88.252:8000",
    "http://192.168.88.244:8000",
    "http://hivplus.local:8000",
    "http://diversehearts.local:8000",
]
CSRF_TRUSTED_ORIGINS.extend(
    item.strip()
    for item in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if item.strip()
)

railway_public_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN')
if railway_public_domain:
    CSRF_TRUSTED_ORIGINS.extend([
        f'https://{railway_public_domain}',
    ])


# Application definition

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',

    'accounts',
    'discovery',
    'messaging',
    'web',
    "channels",
    'interactions',
    
    # API
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_spectacular',
    'api',
    'django_filters',
]
AUTH_USER_MODEL = 'accounts.User'

ASGI_APPLICATION = "core.asgi.application"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'web.middleware.VariantMiddleware',
    "accounts.middleware.LastSeenMiddleware",
    "accounts.middleware.ProfileCompletionMiddleware",
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR,'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'messaging.context_processors.unread_count',
                'web.context_processors.brand_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]



def get_database_url():
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return database_url

    pg_host = os.getenv('PGHOST')
    pg_port = os.getenv('PGPORT')
    pg_database = os.getenv('PGDATABASE')
    pg_user = os.getenv('PGUSER')
    pg_password = os.getenv('PGPASSWORD')

    if all([pg_host, pg_port, pg_database, pg_user, pg_password]):
        return (
            f"postgresql://{quote_plus(pg_user)}:{quote_plus(pg_password)}"
            f"@{pg_host}:{pg_port}/{quote_plus(pg_database)}"
        )

    if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID'):
        raise ImproperlyConfigured(
            "Railway deployment requires DATABASE_URL or all PGHOST, PGPORT, "
            "PGDATABASE, PGUSER, and PGPASSWORD variables."
        )

    return f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}"


# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

default_database_url = get_database_url()

if isinstance(default_database_url, bytes):
    default_database_url = default_database_url.decode('utf-8', errors='ignore')

try:
    DATABASES = {
        'default': dj_database_url.parse(
            default_database_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
except Exception:
    if os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_PROJECT_ID'):
        raise

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }



# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


REDIS_URL = os.getenv('REDIS_URL', '')

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "typing-indicators",
    },
    "presence": {
        "BACKEND": "django_redis.cache.RedisCache" if REDIS_URL else "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": REDIS_URL if REDIS_URL else "presence-cache",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        } if REDIS_URL else {}
    }
}

# Channel Layers - uses InMemory if Redis is not available
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

# Production Security Settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True


# Email Configuration
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST')
    EMAIL_PORT = os.getenv('EMAIL_PORT', 587)
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'support@datingapp.com')

# Allauth / Social Auth Settings
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = 'none'  # Adjust as needed (optional, mandatory)
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = os.getenv('ACCOUNT_DEFAULT_HTTP_PROTOCOL', 'https')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APPS': [{
            'client_id': os.getenv('GOOGLE_CLIENT_ID'),
            'secret': os.getenv('GOOGLE_CLIENT_SECRET'),
            'key': ''
        }]
    },
    'facebook': {
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'AUTH_PARAMS': {'auth_type': 'reauthenticate'},
        'FIELDS': ['id', 'email', 'name', 'first_name', 'last_name', 'picture'],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': False,
        'APPS': [{
            'client_id': os.getenv('FACEBOOK_CLIENT_ID'),
            'secret': os.getenv('FACEBOOK_CLIENT_SECRET'),
            'key': ''
        }]
    }
}

SOCIALACCOUNT_LOGIN_ON_GET = True

# Development helpers
INTERNAL_IPS = [
    "127.0.0.1",
]

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
}

# Simple JWT Configuration
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all in dev, restrict in production
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS',  "http://localhost:8081,http://192.168.88.252:8081,http://192.168.88.244:8081").split(',')

from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-app-variant',
]

# Spectacular Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'Dating App API',
    'DESCRIPTION': 'API documentation for the Dating App React Native integration',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

