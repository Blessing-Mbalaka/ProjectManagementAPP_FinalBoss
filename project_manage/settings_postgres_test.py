"""Isolated local PostgreSQL tests; never uses DATABASE_URL or production."""
import os

from .settings_test import *  # noqa: F403

# A separate loopback-only cluster and database names prevent the test runner
# from creating, flushing or dropping the deployment database.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': '127.0.0.1',
        'PORT': int(os.environ.get('LOCAL_PG_TEST_PORT', '55439')),
        'NAME': 'project_management_pg_checks',
        'USER': 'codex_audit',
        'PASSWORD': '',
        'ATOMIC_REQUESTS': True,
        'TEST': {'NAME': 'test_project_management_pg_checks'},
    },
}
