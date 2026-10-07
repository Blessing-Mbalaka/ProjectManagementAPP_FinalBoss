import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class EmailEnvironmentSettingsTests(SimpleTestCase):
    def test_runtime_environment_controls_smtp_settings(self):
        env = os.environ.copy()
        env.update(
            {
                "DJANGO_SETTINGS_MODULE": "project_manage.settings",
                "EMAIL_HOST": "smtp.environment.test",
                "EMAIL_PORT": "2525",
                "EMAIL_HOST_USER": "environment@example.com",
                "EMAIL_HOST_PASSWORD": "environment-secret",
                "DEFAULT_FROM_EMAIL": "Environment Sender <environment@example.com>",
                "EMAIL_USE_CONSOLE": "False",
                "EMAIL_USE_TLS": "False",
                "EMAIL_USE_SSL": "True",
            }
        )
        script = (
            "from django.conf import settings; "
            "print(settings.EMAIL_HOST); "
            "print(settings.EMAIL_PORT); "
            "print(settings.EMAIL_HOST_USER); "
            "print(settings.EMAIL_HOST_PASSWORD); "
            "print(settings.DEFAULT_FROM_EMAIL); "
            "print(settings.EMAIL_USE_TLS); "
            "print(settings.EMAIL_USE_SSL)"
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(
            result.stdout.strip().splitlines(),
            [
                "smtp.environment.test",
                "2525",
                "environment@example.com",
                "environment-secret",
                "Environment Sender <environment@example.com>",
                "False",
                "True",
            ],
        )
