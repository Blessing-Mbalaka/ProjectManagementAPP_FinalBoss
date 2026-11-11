from pathlib import Path
from smtplib import SMTPAuthenticationError
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from . import backup_service
from .email_health import configuration_problem, email_health
from .models import BackupSchedule, Notification


@override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.example.test', EMAIL_HOST_USER='operator', EMAIL_HOST_PASSWORD='private-password', DEFAULT_FROM_EMAIL='backups@example.test', EMAIL_USE_TLS=True, EMAIL_USE_SSL=False, DB_BACKUP_ALLOW_TEST_EMAIL=False, DB_BACKUP_ENABLED=True)
class BackupEmailHealthTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.it = users.objects.create_user('smtp-it', role='it')
        self.admin = users.objects.create_user('smtp-admin', role='admin')
        self.staff = users.objects.create_user('smtp-staff', role='staff')

    def warnings(self):
        return Notification.objects.filter(title__startswith='IT warning: backup SMTP')

    def test_missing_configuration_warns_it_and_admin_once_without_sending(self):
        with override_settings(EMAIL_HOST_PASSWORD=''), patch.object(backup_service.EmailMessage, 'send') as send:
            self.assertTrue(email_health()['warning'])
            email_health()
            with self.assertRaisesMessage(backup_service.BackupError, 'Configure SMTP'):
                backup_service.create_backup()
        send.assert_not_called()
        self.assertEqual(self.warnings().count(), 1)
        self.assertEqual(set(self.warnings().get().recipients.values_list('pk', flat=True)), {self.it.pk, self.admin.pk})
        self.assertNotIn('private-password', self.warnings().get().body)

    def test_failed_delivery_persists_until_success_and_does_not_expose_exception(self):
        record = {'id': 'a' * 32, 'created_at': '2026-11-11'}
        fake_path = Path('unused')
        with patch.object(Path, 'stat') as stat, patch.object(backup_service, 'archive_payload', return_value=b'archive'):
            stat.return_value.st_size = 7
            for failure in [SMTPAuthenticationError(535, b'private-password'), OSError('private-password')]:
                with patch.object(backup_service.EmailMessage, 'send', side_effect=failure), self.assertRaises(backup_service.BackupError):
                    backup_service._email_archive(record, fake_path, ['recipient@example.test'])
            self.assertEqual(self.warnings().count(), 1)
            self.assertEqual(email_health()['state'], 'failed')
            self.assertNotIn('private-password', self.warnings().get().body)
            with patch.object(backup_service.EmailMessage, 'send', return_value=1):
                backup_service._email_archive(record, fake_path, ['recipient@example.test'])
        self.assertEqual(email_health()['warning'], '')
        self.assertEqual(BackupSchedule.objects.get().email_delivery_state, 'accepted')

    def test_zero_accepted_messages_is_a_failure(self):
        with patch.object(Path, 'stat') as stat, patch.object(backup_service, 'archive_payload', return_value=b'archive'), patch.object(backup_service.EmailMessage, 'send', return_value=0):
            stat.return_value.st_size = 7
            with self.assertRaises(backup_service.BackupError):
                backup_service._email_archive({'id': 'b' * 32, 'created_at': 'now'}, Path('unused'), ['recipient@example.test'])
        self.assertEqual(email_health()['state'], 'failed')

    def test_configuration_fix_requires_delivery_verification(self):
        with override_settings(EMAIL_HOST=''):
            self.assertEqual(email_health()['state'], 'not_configured')
        self.assertEqual(email_health()['state'], 'unverified')
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'):
            self.assertTrue(configuration_problem())
        with override_settings(EMAIL_USE_SSL=True):
            self.assertTrue(configuration_problem())
        # An explicitly configured internal SMTP relay may allow no authentication.
        with override_settings(EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD=''):
            self.assertFalse(configuration_problem())
        with override_settings(DEFAULT_FROM_EMAIL='System Backups <backups@example.test>'):
            self.assertFalse(configuration_problem())

    def test_it_banner_and_notification_are_available_without_email_delivery(self):
        self.client.force_login(self.it)
        with override_settings(EMAIL_HOST=''), patch.object(backup_service.EmailMessage, 'send') as send:
            response = self.client.get(reverse('it_dashboard'))
        self.assertContains(response, 'IT warning')
        self.assertContains(response, 'Backup SMTP is not configured')
        self.assertEqual(self.warnings().count(), 1)
        send.assert_not_called()

    def test_worker_warns_about_missing_smtp_even_before_a_job_is_due(self):
        with override_settings(EMAIL_HOST=''), patch('adminpanel.management.commands.run_backup_jobs.backup_directory'), patch.object(backup_service.EmailMessage, 'send') as send:
            call_command('run_backup_jobs')
            call_command('run_backup_jobs')
        self.assertEqual(self.warnings().count(), 1)
        send.assert_not_called()
