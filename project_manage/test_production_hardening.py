import os
import subprocess
import sys
from pathlib import Path

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.views import defaults
from django.views.csrf import csrf_failure


class ProductionHardeningTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_unknown_route_uses_custom_404_page(self):
        response = self.client.get('/this-page-does-not-exist/', HTTP_HOST='localhost', secure=True)

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'The page you requested could not be found.', status_code=404)

    @override_settings(DEBUG=False)
    def test_bad_request_uses_custom_400_page(self):
        request = RequestFactory().get('/invalid-request/')

        response = defaults.bad_request(request, Exception('private error details'))

        self.assertContains(response, 'The request could not be processed.', status_code=400)
        self.assertNotContains(response, 'private error details', status_code=400)

    @override_settings(DEBUG=False)
    def test_permission_denied_uses_custom_403_page(self):
        request = RequestFactory().get('/restricted/')

        response = defaults.permission_denied(request, Exception('private permission details'))

        self.assertContains(response, 'You do not have permission to access this page.', status_code=403)
        self.assertNotContains(response, 'private permission details', status_code=403)

    @override_settings(DEBUG=False)
    def test_csrf_failure_uses_custom_403_page(self):
        request = RequestFactory().post('/form/')

        response = csrf_failure(request, reason='private CSRF details')

        self.assertContains(
            response,
            'Your security token expired or was invalid.',
            status_code=403,
        )
        self.assertNotContains(response, 'private CSRF details', status_code=403)

    @override_settings(DEBUG=False)
    def test_server_error_uses_custom_500_page(self):
        request = RequestFactory().get('/broken/')

        response = defaults.server_error(request)

        self.assertContains(response, 'Something went wrong on our side.', status_code=500)

    def test_debug_false_enables_environment_driven_security_settings(self):
        env = os.environ.copy()
        env.update(
            {
                'DJANGO_SETTINGS_MODULE': 'project_manage.settings',
                'DEBUG': 'False',
                'SECRET_KEY': 'production-test-secret-key-with-more-than-fifty-unique-characters-123456789',
                'SECURE_SSL_REDIRECT': 'True',
                'SESSION_COOKIE_SECURE': 'True',
                'CSRF_COOKIE_SECURE': 'True',
            }
        )
        script = (
            'from django.conf import settings; '
            'print(settings.SECRET_KEY); '
            'print(settings.SECURE_SSL_REDIRECT); '
            'print(settings.SESSION_COOKIE_SECURE); '
            'print(settings.CSRF_COOKIE_SECURE); '
            'print(settings.SECURE_HSTS_SECONDS); '
            'print(settings.SECURE_HSTS_INCLUDE_SUBDOMAINS); '
            'print(settings.SECURE_HSTS_PRELOAD); '
            'print(settings.SESSION_COOKIE_AGE)'
        )

        result = subprocess.run(
            [sys.executable, '-c', script],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(
            result.stdout.strip().splitlines(),
            [
                env['SECRET_KEY'],
                'True',
                'True',
                'True',
                '3600',
                'False',
                'False',
                '1209600',
            ],
        )
