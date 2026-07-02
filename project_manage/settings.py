
from pathlib import Path
import os
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-_0c$9attqx23_v=(t13^$f8!z)yyn+kz+^)%a=)5r)sg_r8b0u'

# Load .env file and let it override any stale shell-level values on the server.
load_dotenv(os.path.join(BASE_DIR, 'project_manage', '.env'), override=True)


def env_flag(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_flag('DEBUG', True)

# Enhanced ALLOWED_HOSTS configuration for Render, Azure Container Apps, and local development
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '.onrender.com'
    'http://162.35.167.180:67/',
]



# Email config: use SMTP unless EMAIL_USE_CONSOLE is true
EMAIL_USE_CONSOLE = env_flag('EMAIL_USE_CONSOLE', False)
if EMAIL_USE_CONSOLE:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = env_flag('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_flag('EMAIL_USE_SSL', False)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = "udoc jpes dnof azku"
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'noreply@yourdomain.com')
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '5'))
ENABLE_CRM_ALERT_EMAILS = env_flag('ENABLE_CRM_ALERT_EMAILS', False)




# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'adminpanel',
    'projects',
    'users',
    'manager',
]


# Hardcoded SQLite database for now.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Previous PostgreSQL config kept here for reference only:
# DATABASE_URL=postgresql://...
# DB_NAME=...
# DB_PASSWORD=...
# DB_PORT=5432
# DB_USER_NAME=...
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# For development/testing, disable CSRF if needed (NOT recommended for production)
if DEBUG and env_flag('DISABLE_CSRF', False):
    MIDDLEWARE = [m for m in MIDDLEWARE if m != 'django.middleware.csrf.CsrfViewMiddleware']

ROOT_URLCONF = 'project_manage.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'project_manage.wsgi.application'

AUTH_USER_MODEL = 'users.CustomUser'

# Database configuration for both Docker and Azure
# DATABASES = {
#     'default': dj_database_url.config(
#         default=os.getenv(
#             'DATABASE_URL',
#             'postgres://postgres:postgres@db:5432/project_management'  # <-- NOTE the host is 'db' here
#         ),
#         conn_max_age=600,
#         ssl_require=False
#     )
# }




# Password validation
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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Johannesburg'
USE_I18N = True
USE_TZ = True

# Static files configuration
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")] if os.path.exists(os.path.join(BASE_DIR, "static")) else []
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Use WhiteNoise for static files
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# SSL/HTTPS production security logic removed for local and production simplicity

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = "/login"
LOGOUT_REDIRECT_URL = "/login/"

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}
