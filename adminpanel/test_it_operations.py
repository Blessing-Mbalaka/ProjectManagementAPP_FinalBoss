import json
import sqlite3
import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from adminpanel import backup_service as service
from adminpanel.models import BackupSchedule, SecurityEvent


class NativeSnapshotTests(SimpleTestCase):
    def setUp(self):
        root = Path(settings.BASE_DIR) / 'test_artifacts' / 'tmp'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / 'source.sqlite3'
        with sqlite3.connect(self.database) as connection:
            connection.execute('CREATE TABLE sample (value TEXT)')
            connection.execute("INSERT INTO sample VALUES ('before')")
        connection.close()
        self.config = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': self.database}
        self.overrides = override_settings(DB_BACKUP_DIR=self.root / 'backups', DB_BACKUP_ENABLED=True, DB_RESTORE_ENABLED=True, DB_MAINTENANCE_MODE=True, DB_BACKUP_KEEP_LOCAL=True, DB_BACKUP_ALLOW_TEST_EMAIL=True, DEBUG=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        for name, value in [('_database', (self.config, 'sqlite3')), ('_schema', ['test.0001']), ('_email_recipients', ['backup@example.test'])]:
            mocker = patch.object(service, name, return_value=value)
            mocker.start()
            self.addCleanup(mocker.stop)
        for name, value in [('_record_snapshot', None), ('_snapshot_records', [])]:
            mocker = patch.object(service, name, return_value=value)
            mocker.start()
            self.addCleanup(mocker.stop)

    def test_native_backup_and_restore_roundtrip_and_safety_copy(self):
        snapshot = service.create_backup('it-tester')
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE sample SET value='after'")
        connection.close()
        with patch.object(service.connections, 'close_all'), patch.object(service, '_after_restore') as finish:
            safety = service.restore_backup(snapshot['id'], 'it-tester', 'RESTORE ' + snapshot['id'])
        finish.assert_called_once()
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute('SELECT value FROM sample').fetchone()[0], 'before')
        connection.close()
        _, safety_path = service.get_backup(safety['id'], verify=True)
        with sqlite3.connect(safety_path) as connection:
            self.assertEqual(connection.execute('SELECT value FROM sample').fetchone()[0], 'after')
        connection.close()
        self.assertEqual(len(service.list_backups()), 2)
        self.assertIn('restore_completed', (service.backup_directory() / 'operations.jsonl').read_text())

    def test_corrupt_backup_and_wrong_confirmation_are_refused(self):
        snapshot = service.create_backup('it-tester')
        with self.assertRaises(service.BackupError):
            service.restore_backup(snapshot['id'], 'it-tester', 'RESTORE wrong')
        _, path = service.get_backup(snapshot['id'])
        path.write_bytes(b'corrupt')
        with self.assertRaisesMessage(service.BackupError, 'checksum'):
            service.restore_backup(snapshot['id'], 'it-tester', 'RESTORE ' + snapshot['id'])

    def test_restore_gates_and_schema_mismatch(self):
        snapshot = service.create_backup('it-tester')
        with override_settings(DB_MAINTENANCE_MODE=False), self.assertRaises(service.BackupError):
            service.restore_backup(snapshot['id'], 'it-tester', 'RESTORE ' + snapshot['id'])
        with patch.object(service, '_schema', return_value=['new.0002']), self.assertRaisesMessage(service.BackupError, 'migration'):
            service.restore_backup(snapshot['id'], 'it-tester', 'RESTORE ' + snapshot['id'])
        with override_settings(DB_BACKUP_ENABLED=False), self.assertRaises(service.BackupError):
            service.create_backup('it-tester')

    def test_path_traversal_and_overlapping_operations_are_refused(self):
        with self.assertRaises(service.BackupError):
            service.get_backup('../source')
        with service.operation_lock(), self.assertRaises(service.BackupError):
            service.create_backup('it-tester')
        with override_settings(DB_BACKUP_DIR=Path(settings.MEDIA_ROOT) / 'backups'), self.assertRaises(service.BackupError):
            service.backup_directory()

    def test_postgres_uses_native_tool_and_password_only_in_environment(self):
        config = {'NAME': 'app', 'HOST': 'localhost', 'PORT': '5432', 'USER': 'operator', 'PASSWORD': 'private-value', 'OPTIONS': {'sslmode': 'require'}}
        with patch.object(service.subprocess, 'run') as run:
            service._run_pg(['pg_dump', '--dbname', 'app'], config)
        args, kwargs = run.call_args
        self.assertNotIn('private-value', str(args))
        self.assertEqual(kwargs['env']['PGPASSWORD'], 'private-value')
        self.assertEqual(kwargs['env']['PGSSLMODE'], 'require')
        self.assertFalse(kwargs['shell'])
        with patch.object(service.subprocess, 'run', side_effect=OSError('private-value')), self.assertRaises(service.BackupError) as error:
            service._run_pg(['pg_dump'], config)
        self.assertNotIn('private-value', str(error.exception))

    def test_hourly_daily_weekly_schedule_calculation(self):
        now = datetime(2026, 11, 11, 12, 15, tzinfo=ZoneInfo('Africa/Johannesburg'))
        self.assertEqual(service.next_backup_run('hourly', time(2), 0, now).hour, 13)
        self.assertEqual(service.next_backup_run('daily', time(2), 0, now).day, 12)
        weekly = service.next_backup_run('weekly', time(2), 0, now)
        self.assertEqual(weekly.weekday(), 0)
        self.assertGreater(weekly, now)


    def test_email_archive_is_restorable_without_retaining_server_database(self):
        import io
        import zipfile
        from django.core import mail
        from django.core.files.uploadedfile import SimpleUploadedFile
        with override_settings(DB_BACKUP_KEEP_LOCAL=False):
            snapshot = service.create_backup('email-tester')
        self.assertFalse((service.backup_directory() / snapshot['filename']).exists())
        self.assertEqual(len(mail.outbox[-1].attachments), 1)
        self.assertEqual(mail.outbox[-1].bcc, ['backup@example.test'])
        attachment = mail.outbox[-1].attachments[0][1]
        with zipfile.ZipFile(io.BytesIO(attachment)) as archive:
            self.assertIn('manifest.json', archive.namelist())
            self.assertIn(snapshot['filename'], archive.namelist())
        upload = SimpleUploadedFile('received.zip', attachment, content_type='application/zip')
        imported = service.import_backup_archive(upload, 'email-tester')
        self.assertEqual(imported['id'], snapshot['id'])
        service.get_backup(imported['id'], verify=True)

    def test_failed_email_prevents_completed_snapshot_and_restore(self):
        with patch.object(service.EmailMessage, 'send', return_value=0), self.assertRaises(service.BackupError):
            service.create_backup('email-tester')
        self.assertEqual(service.list_backups(), [])
        snapshot = service.create_backup('email-tester')
        with patch.object(service.EmailMessage, 'send', side_effect=OSError('SMTP failure')), patch.object(service.connections, 'close_all'), self.assertRaises(service.BackupError):
            service.restore_backup(snapshot['id'], 'email-tester', 'RESTORE ' + snapshot['id'])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute('SELECT value FROM sample').fetchone()[0], 'before')
        connection.close()

    def test_email_size_limit_and_bad_import_are_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        with override_settings(DB_BACKUP_MAX_EMAIL_BYTES=1), self.assertRaises(service.BackupError):
            service.create_backup('email-tester')
        with self.assertRaises(service.BackupError):
            service.import_backup_archive(SimpleUploadedFile('invalid.zip', b'invalid'), 'email-tester')


    def test_disaster_recovery_target_requires_explicit_operator_setting(self):
        record = {'database': service._identity({'NAME': 'original-database'})}
        destination = {'NAME': 'replacement-database'}
        self.assertFalse(service._database_matches(record, destination))
        with override_settings(DB_RESTORE_ALLOW_DIFFERENT_DATABASE=True, DB_RESTORE_ENABLED=True, DB_MAINTENANCE_MODE=True):
            self.assertTrue(service._database_matches(record, destination))
        with override_settings(DB_RESTORE_ALLOW_DIFFERENT_DATABASE=True, DB_MAINTENANCE_MODE=False):
            self.assertFalse(service._database_matches(record, destination))


    def test_recovery_refuses_archives_when_payroll_keys_are_missing(self):
        snapshot = service.create_backup('it-tester')
        with override_settings(SALARY_ENCRYPTION_KEYS=[]), self.assertRaisesMessage(service.BackupError, 'Salary encryption keys'):
            service.restore_backup(snapshot['id'], 'it-tester', 'RESTORE ' + snapshot['id'])


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ITOperationsTests(TestCase):
    def setUp(self):
        root = Path(settings.BASE_DIR) / 'test_artifacts' / 'tmp'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.overrides = override_settings(DB_BACKUP_DIR=Path(self.temp.name), DB_BACKUP_ENABLED=True)
        self.overrides.enable()
        self.addCleanup(self.overrides.disable)
        U = get_user_model()
        self.it = U.objects.create_user('it-operator', password='local-password', role='it', email='it@example.test')
        self.staff = U.objects.create_user('it-test-staff', password='local-password', role='staff')
        self.client.force_login(self.it)

    def test_it_dashboard_and_monitoring_access_without_business_admin_rights(self):
        for name in ['it_dashboard', 'page_visit_audit', 'security_event_audit']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
        page = self.client.get(reverse('it_dashboard'))
        self.assertContains(page, 'IT Operations')
        self.assertNotContains(page, 'href="' + reverse('finance') + '"')
        self.assertNotContains(page, 'href="' + reverse('manage_users') + '"')
        self.assertNotEqual(self.client.get(reverse('manage_users')).status_code, 200)
        from users.views import _role_home_name
        self.assertEqual(_role_home_name(self.it), 'it_dashboard')

    def test_other_roles_cannot_access_operations(self):
        U = get_user_model()
        for role in ['staff', 'student', 'supervisor', 'manager', 'financialadmin', 'dean', 'centrehead', 'overseer']:
            user = U.objects.create_user('deny-' + role, role=role)
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('it_dashboard')).status_code, 403)
            self.assertEqual(self.client.post(reverse('it_backup_now')).status_code, 403)
            self.assertEqual(self.client.post(reverse('it_restore')).status_code, 403)
            self.assertEqual(self.client.post(reverse('it_backup_import')).status_code, 403)
            self.assertEqual(self.client.get(reverse('it_backup_download', args=['a' * 32])).status_code, 403)

    def test_it_can_resolve_system_security_event(self):
        event = SecurityEvent.objects.create(user=self.staff, event_type='login', reason='Local review')
        self.assertEqual(self.client.post(reverse('security_event_audit'), {'event_id': event.pk}).status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.status, 'resolved')

    def test_schedule_and_worker_run_due_job_only_once(self):
        response = self.client.post(reverse('it_dashboard'), {'enabled': 'on', 'frequency': 'daily', 'run_at': '02:30', 'weekday': '1', 'recipients': [self.it.pk]})
        self.assertEqual(response.status_code, 302)
        job = BackupSchedule.objects.get(key='database')
        self.assertTrue(job.enabled)
        job.next_run = timezone.now() - timedelta(minutes=1)
        job.save()
        with patch('adminpanel.management.commands.run_backup_jobs.create_backup', return_value={'id': 'snapshot'}) as backup:
            call_command('run_backup_jobs')
            call_command('run_backup_jobs')
        backup.assert_called_once()
        job.refresh_from_db()
        self.assertIn('Completed', job.last_result)
        self.assertGreater(job.next_run, timezone.now())
        self.assertTrue((Path(self.temp.name) / 'worker-heartbeat').exists())

    def test_invalid_weekday_and_disabled_environment_refuse_enabling_schedule(self):
        response = self.client.post(reverse('it_dashboard'), {'enabled': 'on', 'frequency': 'weekly', 'run_at': '02:30', 'weekday': '10', 'recipients': [self.it.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BackupSchedule.objects.get().enabled)
        with override_settings(DB_BACKUP_ENABLED=False):
            response = self.client.post(reverse('it_dashboard'), {'enabled': 'on', 'frequency': 'daily', 'run_at': '02:30', 'weekday': '1', 'recipients': [self.it.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BackupSchedule.objects.get().enabled)

    def test_restore_requires_password_and_is_post_only(self):
        with patch('adminpanel.it_views.restore_backup') as restore:
            response = self.client.post(reverse('it_restore'), {'password': 'wrong', 'backup_id': 'a' * 32})
        self.assertEqual(response.status_code, 302)
        restore.assert_not_called()
        self.assertEqual(self.client.get(reverse('it_restore')).status_code, 405)
        self.assertEqual(self.client.get(reverse('it_backup_now')).status_code, 405)

    def test_public_registration_cannot_create_it(self):
        self.client.logout()
        response = self.client.post(reverse('register'), {'username': 'rogue-it', 'role': 'it', 'password1': 'TestPassword!2026', 'password2': 'TestPassword!2026'})
        self.assertFalse(get_user_model().objects.filter(username='rogue-it').exists())


    def test_after_restore_disables_schedules_and_invalidates_sessions(self):
        from django.contrib.sessions.models import Session
        BackupSchedule.objects.create(key='database', enabled=True, next_run=timezone.now())
        self.assertTrue(Session.objects.exists())
        service._after_restore()
        self.assertFalse(Session.objects.exists())
        job = BackupSchedule.objects.get()
        self.assertFalse(job.enabled)
        self.assertIsNone(job.next_run)

    def test_operations_actions_have_csrf_protection(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.it)
        self.assertEqual(client.post(reverse('it_backup_now')).status_code, 403)
        self.assertEqual(client.post(reverse('it_restore')).status_code, 403)


    def test_downloaded_recovery_package_contains_manifest_and_database(self):
        import io
        import zipfile
        record = {'id': 'b' * 32, 'filename': 'b' * 32 + '.sqlite3'}
        path = Path(self.temp.name) / record['filename']
        path.write_bytes(b'local snapshot')
        with patch('adminpanel.it_views.get_backup', return_value=(record, path)):
            response = self.client.get(reverse('it_backup_download', args=[record['id']]))
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as archive:
            self.assertEqual(archive.read(record['filename']), b'local snapshot')
            self.assertEqual(json.loads(archive.read('manifest.json'))['id'], record['id'])
