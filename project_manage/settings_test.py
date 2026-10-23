"""
Test settings for Django test suite
Extends production settings with test-specific configuration
"""
import os
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'test-only-secret-key-not-for-production-12345678901234567890')

from .settings import *  # noqa

TEST_RUNNER = 'project_manage.test_runner.ApplicationDiscoverRunner'
DEBUG = True
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# Use a file-backed SQLite database that is isolated from production.
TEST_DB_PATH = Path(BASE_DIR) / 'test_artifacts' / 'test.db'
TEST_SUITE_DB_PATH = Path(BASE_DIR) / 'test_artifacts' / 'test_suite.db'
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': TEST_DB_PATH,
        'ATOMIC_REQUESTS': True,
        'TEST': {
            # Never let Django's test runner create, flush, or delete the
            # persistent demo database used by the local review server.
            'NAME': TEST_SUITE_DB_PATH,
        },
    }
}

# Use console email backend to capture emails in tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
EMAIL_HOST = 'localhost'
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
EMAIL_FROM_USER = 'test@example.com'

# Disable password validation in tests for faster user creation
AUTH_PASSWORD_VALIDATORS = []

# Use simple password hasher for faster test execution
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable CSRF for API testing
CSRF_TRUSTED_ORIGINS = ['http://testserver', 'http://127.0.0.1:8000']

# Logging configuration for tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
}

# Simplified media files for tests
MEDIA_URL = '/test_media/'
MEDIA_ROOT = '/tmp/test_media/'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = '/tmp/test_static/'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

# Reduce logging noise
logging_config = LOGGING
