from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from adminpanel.models import Notification, ResearchCentre, SecurityEvent
from users.models import CustomUser


class SecurityMonitoringTests(TestCase):
    def setUp(self):
        cache.clear()
        self.centre = ResearchCentre.objects.create(name='Security Test Centre')
        self.staff = CustomUser.objects.create_user(
            username='security-staff',
            password='OldSecurePass!2026',
            role='staff',
            research_centre=self.centre,
        )
        self.head = CustomUser.objects.create_user(
            username='security-head',
            password='pass',
            role='centrehead',
            research_centre=self.centre,
        )
        self.admin = CustomUser.objects.create_user(
            username='security-admin',
            password='pass',
            role='admin',
        )

    @override_settings(
        SECURITY_SUSPICIOUS_LOGIN_START_HOUR=0,
        SECURITY_SUSPICIOUS_LOGIN_END_HOUR=0,
    )
    def test_unusual_login_prompts_user_and_notifies_security_recipients(self):
        response = self.client.post(reverse('login'), {
            'username': self.staff.username,
            'password': 'OldSecurePass!2026',
        }, HTTP_USER_AGENT='Test Browser', REMOTE_ADDR='192.0.2.10')

        event = SecurityEvent.objects.get(user=self.staff, event_type='login')
        self.assertTrue(event.is_suspicious)
        self.assertEqual(event.status, 'open')
        self.assertRedirects(response, reverse('security_event_review', args=[event.id]))
        self.assertTrue(Notification.objects.filter(recipients=self.staff, title__icontains='Was this you').exists())
        self.assertTrue(Notification.objects.filter(recipients=self.admin, title__icontains='Security flag').exists())
        self.assertTrue(Notification.objects.filter(recipients=self.head, title__icontains='Security flag').exists())

    @override_settings(
        SECURITY_SUSPICIOUS_LOGIN_START_HOUR=0,
        SECURITY_SUSPICIOUS_LOGIN_END_HOUR=0,
    )
    def test_user_can_confirm_suspicious_login(self):
        self.client.post(reverse('login'), {
            'username': self.staff.username,
            'password': 'OldSecurePass!2026',
        })
        event = SecurityEvent.objects.get(user=self.staff, event_type='login')

        response = self.client.post(reverse('security_event_review', args=[event.id]), {'action': 'confirm'})

        event.refresh_from_db()
        self.assertEqual(event.status, 'confirmed')
        self.assertIsNotNone(event.reviewed_at)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertRedirects(
            response,
            reverse('dashboard'),
            fetch_redirect_response=False,
        )

        security_center = self.client.get(reverse('security_center'))
        self.assertContains(security_center, 'Continue to my dashboard')
        self.assertContains(security_center, f'href="{reverse("dashboard")}"')

    @override_settings(
        SECURITY_SUSPICIOUS_LOGIN_START_HOUR=0,
        SECURITY_SUSPICIOUS_LOGIN_END_HOUR=0,
    )
    def test_centre_head_confirmation_returns_to_requested_security_log(self):
        security_log_url = reverse('security_event_audit')
        login_url = f"{reverse('login')}?next={security_log_url}"

        login_page = self.client.get(login_url)
        self.assertContains(login_page, f'name="next" value="{security_log_url}"')

        login_response = self.client.post(reverse('login'), {
            'username': self.head.username,
            'password': 'pass',
            'next': security_log_url,
        })
        event = SecurityEvent.objects.get(user=self.head, event_type='login')
        self.assertRedirects(
            login_response,
            f'{reverse("security_event_review", args=[event.id])}?next=%2Fadminpanel%2Factivity%2Fsecurity%2F',
            fetch_redirect_response=False,
        )

        confirmation = self.client.post(
            reverse('security_event_review', args=[event.id]),
            {'action': 'confirm', 'next': security_log_url},
            follow=True,
        )

        event.refresh_from_db()
        self.assertEqual(event.status, 'confirmed')
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(confirmation.status_code, 200)
        self.assertEqual(confirmation.redirect_chain[-1][0], security_log_url)
        self.assertContains(confirmation, 'Security Alerts')

    @override_settings(
        SECURITY_SUSPICIOUS_LOGIN_START_HOUR=0,
        SECURITY_SUSPICIOUS_LOGIN_END_HOUR=0,
    )
    def test_user_can_change_password_from_security_alert(self):
        self.client.post(reverse('login'), {
            'username': self.staff.username,
            'password': 'OldSecurePass!2026',
        })
        event = SecurityEvent.objects.get(user=self.staff, event_type='login')
        self.client.post(reverse('security_event_review', args=[event.id]), {'action': 'secure'})

        response = self.client.post(reverse('security_password_change'), {
            'old_password': 'OldSecurePass!2026',
            'new_password1': 'NewSecurePass!2026',
            'new_password2': 'NewSecurePass!2026',
        })

        self.staff.refresh_from_db()
        event.refresh_from_db()
        self.assertTrue(self.staff.check_password('NewSecurePass!2026'))
        self.assertEqual(event.status, 'secured')
        self.assertRedirects(response, reverse('security_center'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_denied_assigned_page_is_flagged_without_blocking_permission_response(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse('page_visit_audit'), REMOTE_ADDR='192.0.2.20')

        self.assertEqual(response.status_code, 403)
        event = SecurityEvent.objects.get(user=self.staff, event_type='access_denied')
        self.assertEqual(event.path, reverse('page_visit_audit'))
        self.assertEqual(event.status, 'open')

    @override_settings(SECURITY_REQUEST_LIMIT=3, SECURITY_REQUEST_WINDOW_SECONDS=60)
    def test_request_burst_is_flagged_but_requests_still_complete(self):
        self.client.force_login(self.staff)
        cache.clear()

        responses = [self.client.get(reverse('dashboard')) for _ in range(3)]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        event = SecurityEvent.objects.get(user=self.staff, event_type='request_burst')
        self.assertEqual(event.request_count, 3)
        self.assertEqual(event.severity, 'high')

    @override_settings(SECURITY_FAILED_LOGIN_LIMIT=3, SECURITY_FAILED_LOGIN_WINDOW_SECONDS=600)
    def test_repeated_failed_logins_are_flagged(self):
        cache.clear()
        for _ in range(3):
            response = self.client.post(reverse('login'), {
                'username': self.staff.username,
                'password': 'incorrect-password',
            }, REMOTE_ADDR='192.0.2.30')
            self.assertEqual(response.status_code, 200)

        event = SecurityEvent.objects.get(user=self.staff, event_type='failed_login_burst')
        self.assertEqual(event.request_count, 3)
        self.assertTrue(Notification.objects.filter(recipients=self.staff, title__icontains='Was this you').exists())

    def test_security_log_is_admin_and_centre_head_scoped(self):
        SecurityEvent.objects.create(
            user=self.staff,
            event_type='access_denied',
            severity='medium',
            reason='Test event',
        )
        self.client.force_login(self.head)
        head_response = self.client.get(reverse('security_event_audit'))
        self.assertEqual(head_response.status_code, 200)
        self.assertContains(head_response, self.staff.username)

        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse('security_event_audit'))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, self.staff.username)

    def test_logged_out_security_page_uses_the_real_login_route(self):
        response = self.client.get(reverse('security_event_audit'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('security_event_audit')}",
            fetch_redirect_response=False,
        )
