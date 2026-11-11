"""Dedicated local-only operations demo, never the production DATABASE_URL."""
from .settings_test import *

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'test_artifacts' / 'it_local.db'}}
DB_BACKUP_ENABLED = True
DB_BACKUP_DIR = BASE_DIR / 'test_artifacts' / 'it_operations' / 'backups'
DB_RESTORE_ENABLED = True
DB_MAINTENANCE_MODE = True
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}

# Capture real MIME messages locally; do not send mail to real accounts.
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = BASE_DIR / 'test_artifacts' / 'it_operations' / 'test_mailbox'
DB_BACKUP_ALLOW_TEST_EMAIL = True
DB_BACKUP_KEEP_LOCAL = False
