"""
Test settings for Django test suite
Extends production settings with test-specific configuration
"""
from .settings import *  # noqa

# Use in-memory SQLite database for tests (fast, no setup required)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'ATOMIC_REQUESTS': True,
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

# Disable migrations for test speed
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

MIGRATION_MODULES = DisableMigrations()

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

# Reduce logging noise
logging_config = LOGGING
