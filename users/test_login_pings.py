import io
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.db import OperationalError

from adminpanel.models import Notification
from users.login_pings import ping_body, send_login_pings, run_weekly_login_pings, _database_operation
from users.models import LoginPingDelivery


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DB_BACKUP_ALLOW_TEST_EMAIL=True, DEBUG=True, TIME_ZONE='Africa/Johannesburg')
class LoginPingTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 11, 10, tzinfo=ZoneInfo('Africa/Johannesburg'))
        self.user = get_user_model().objects.create_user('ping-user', email='person@example.test', first_name='Alex', last_login=self.now - timedelta(days=12), date_joined=self.now - timedelta(days=30))

    def test_preview_does_not_send_or_reserve(self):
        result = send_login_pings(now=self.now)
        self.assertEqual(result['eligible'], 1)
        self.assertEqual(LoginPingDelivery.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        output = io.StringIO()
        call_command('send_login_pings', stdout=output)
        self.assertIn('PREVIEW', output.getvalue())

    def test_send_personalises_actual_days_and_date_without_links(self):
        result = send_login_pings(send=True, now=self.now)
        self.assertEqual(result['accepted'], 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['person@example.test'])
        self.assertIn('Hi Alex', email.body)
        self.assertIn('12 days', email.body)
        self.assertIn('30 October 2026', email.body)
        self.assertIn('We are getting concerned', email.body)
        self.assertNotIn('http', email.body)
        self.assertNotIn('onrender', email.body)
        self.assertEqual(LoginPingDelivery.objects.get().status, 'accepted')

    def test_today_yesterday_and_never_logged_in_are_honest(self):
        self.user.last_login = self.now
        self.assertIn('last logged in today', ping_body(self.user, self.now))
        self.assertNotIn('getting concerned', ping_body(self.user, self.now))
        self.user.last_login = self.now - timedelta(days=1)
        self.assertIn('for 1 day.', ping_body(self.user, self.now))
        self.user.last_login = None
        body = ping_body(self.user, self.now)
        self.assertIn('have not logged in yet', body)
        self.assertIn('created 30 days ago', body)
        self.assertNotIn('last login was', body)

    def test_retries_same_week_do_not_duplicate_but_next_week_sends(self):
        send_login_pings(send=True, now=self.now)
        result = send_login_pings(send=True, now=self.now + timedelta(days=1))
        self.assertEqual(result['already_processed'], 1)
        self.assertEqual(len(mail.outbox), 1)
        result = send_login_pings(send=True, now=self.now + timedelta(days=7))
        self.assertEqual(result['accepted'], 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_disabled_accounts_and_invalid_addresses_are_skipped(self):
        users = get_user_model()
        users.objects.create_user('ping-inactive', email='inactive@example.test', is_active=False)
        users.objects.create_user('ping-invalid', email='invalid')
        users.objects.create_user('ping-empty', email='')
        result = send_login_pings(send=True, now=self.now)
        self.assertEqual(result['active'], 3)
        self.assertEqual(result['invalid_email'], 2)
        self.assertEqual(result['accepted'], 1)

    def test_uncertain_send_is_not_retried_and_warns_it(self):
        operator = get_user_model().objects.create_user('ping-it', role='it', email='it@example.test')
        with patch('users.login_pings.EmailMessage.send', side_effect=OSError('private-password')) as send:
            result = send_login_pings(send=True, now=self.now)
        self.assertEqual(result['uncertain'], 1)
        self.assertEqual(result['not_attempted'], 1)
        send.assert_called_once()
        delivery = LoginPingDelivery.objects.get(user=self.user)
        self.assertEqual(delivery.status, 'uncertain')
        notice = Notification.objects.get(title='IT warning: login check-in email failed')
        self.assertIn(operator, notice.recipients.all())
        self.assertNotIn('private-password', notice.body)
        # Only the never-attempted account can be sent on the next invocation.
        result = send_login_pings(send=True, now=self.now)
        self.assertEqual(result['already_processed'], 1)
        self.assertEqual(result['accepted'], 1)

    def test_missing_smtp_stops_before_reservations(self):
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'), self.assertRaisesMessage(ValueError, 'SMTP is not configured'):
            send_login_pings(send=True, now=self.now)
        self.assertEqual(LoginPingDelivery.objects.count(), 0)

    def test_calendar_days_use_local_timezone(self):
        # One minute apart across local midnight is one calendar day.
        self.user.last_login = datetime(2026, 11, 10, 23, 59, tzinfo=ZoneInfo('Africa/Johannesburg'))
        now = datetime(2026, 11, 11, 0, 0, tzinfo=ZoneInfo('Africa/Johannesburg'))
        self.assertIn('for 1 day.', ping_body(self.user, now))

    @override_settings(LOGIN_PINGS_ENABLED=True)
    def test_weekly_worker_runs_only_monday_after_nine_and_once_per_week(self):
        monday = datetime(2026, 11, 16, 9, tzinfo=ZoneInfo('Africa/Johannesburg'))
        self.assertIsNone(run_weekly_login_pings(monday - timedelta(hours=1)))
        self.assertIsNone(run_weekly_login_pings(monday - timedelta(days=1)))
        self.assertEqual(run_weekly_login_pings(monday)['accepted'], 1)
        self.assertIsNone(run_weekly_login_pings(monday + timedelta(minutes=1)))
        self.assertEqual(run_weekly_login_pings(monday + timedelta(days=7))['accepted'], 1)

    @override_settings(LOGIN_PINGS_ENABLED=False)
    def test_weekly_worker_is_opt_in(self):
        self.assertIsNone(run_weekly_login_pings(self.now))
        self.assertFalse(LoginPingDelivery.objects.exists())

    def test_database_reconnect_retries_only_the_database_operation(self):
        operation = Mock(side_effect=[OperationalError('connection closed'), 'saved'])
        with patch('users.login_pings.connections') as connections:
            self.assertEqual(_database_operation(operation), 'saved')
        self.assertEqual(operation.call_count, 2)
        connections.__getitem__.return_value.close.assert_called_once()

    def test_reconnect_after_send_does_not_send_twice(self):
        original = LoginPingDelivery.save
        disconnected = False

        def save(delivery, *args, **kwargs):
            nonlocal disconnected
            if delivery.status == 'accepted' and not disconnected:
                disconnected = True
                raise OperationalError('connection closed')
            return original(delivery, *args, **kwargs)

        with patch.object(LoginPingDelivery, 'save', save), patch('users.login_pings.connections'):
            self.assertEqual(send_login_pings(send=True, now=self.now)['accepted'], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(LoginPingDelivery.objects.get().status, 'accepted')
