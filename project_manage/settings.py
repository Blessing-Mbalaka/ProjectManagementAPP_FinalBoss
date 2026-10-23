
from pathlib import Path
import os
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# Load local development values without overriding environment variables supplied
# by the hosting platform.
load_dotenv(os.path.join(BASE_DIR, 'project_manage', '.env'), override=False)


def env_flag(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_flag('DEBUG', True)

DEVELOPMENT_SECRET_KEY = 'django-insecure-_0c$9attqx23_v=(t13^$f8!z)yyn+kz+^)%a=)5r)sg_r8b0u'
SECRET_KEY = os.getenv('SECRET_KEY', DEVELOPMENT_SECRET_KEY if DEBUG else '')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY must be set when DEBUG=False.')

# Enhanced ALLOWED_HOSTS configuration for Render, Azure Container Apps, and local development
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '.onrender.com',
    '162.35.167.180',
]

# Render terminates TLS at its proxy; trust it so Django sees requests as HTTPS
# and Origin/Referer checks for CSRF match the public https host.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
    *[o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()],
]

# Production transport and cookie hardening. All values remain environment
# configurable for reverse proxies and controlled rollout.
SECURE_SSL_REDIRECT = env_flag('SECURE_SSL_REDIRECT', not DEBUG)
SESSION_COOKIE_SECURE = env_flag('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_flag('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '3600' if not DEBUG else '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_flag('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_flag('SECURE_HSTS_PRELOAD', False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

# Keep the existing two-week session lifetime explicit. Sessions are stored in
# the database, use HTTP-only cookies, and do not expire merely on browser close.
SESSION_COOKIE_AGE = int(os.getenv('SESSION_COOKIE_AGE', '1209600'))
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_flag('SESSION_EXPIRE_AT_BROWSER_CLOSE', False)
SESSION_SAVE_EVERY_REQUEST = env_flag('SESSION_SAVE_EVERY_REQUEST', False)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# Email config: use SMTP unless EMAIL_USE_CONSOLE is true.
EMAIL_USE_CONSOLE = env_flag('EMAIL_USE_CONSOLE', False)
EMAIL_BACKEND = (
    'django.core.mail.backends.console.EmailBackend'
    if EMAIL_USE_CONSOLE
    else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = env_flag('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_flag('EMAIL_USE_SSL', False)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'webmaster@localhost')
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '10'))
# ENABLE_CRM_ALERT_EMAILS = env_flag('ENABLE_CRM_ALERT_EMAILS', False)




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


# Use Render/Azure DATABASE_URL when available, otherwise fall back to local SQLite.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        ssl_require=False,
    )
}
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'adminpanel.middleware.PageVisitAuditMiddleware',
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

# Security activity monitoring. These values flag activity for review without
# throttling or interrupting legitimate work.
SECURITY_SUSPICIOUS_LOGIN_START_HOUR = int(os.getenv('SECURITY_SUSPICIOUS_LOGIN_START_HOUR', '0'))
SECURITY_SUSPICIOUS_LOGIN_END_HOUR = int(os.getenv('SECURITY_SUSPICIOUS_LOGIN_END_HOUR', '5'))
SECURITY_FAILED_LOGIN_LIMIT = int(os.getenv('SECURITY_FAILED_LOGIN_LIMIT', '5'))
SECURITY_FAILED_LOGIN_WINDOW_SECONDS = int(os.getenv('SECURITY_FAILED_LOGIN_WINDOW_SECONDS', '600'))
SECURITY_REQUEST_LIMIT = int(os.getenv('SECURITY_REQUEST_LIMIT', '120'))
SECURITY_REQUEST_WINDOW_SECONDS = int(os.getenv('SECURITY_REQUEST_WINDOW_SECONDS', '60'))
SECURITY_ACCESS_ALERT_COOLDOWN_SECONDS = int(os.getenv('SECURITY_ACCESS_ALERT_COOLDOWN_SECONDS', '900'))

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

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/overview/'
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
