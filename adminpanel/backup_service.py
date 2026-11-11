"""Private native database snapshots. No shell commands or user supplied paths."""
from contextlib import contextmanager, closing
from datetime import timedelta
from hashlib import sha256
import io
import zipfile
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from uuid import uuid4, UUID

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone
from .email_health import configuration_problem, update_email_status


class BackupError(Exception):
    pass


def backup_directory():
    root = Path(settings.DB_BACKUP_DIR).resolve()
    # Never publish database snapshots through media/static serving.
    for public in [getattr(settings, 'MEDIA_ROOT', ''), getattr(settings, 'STATIC_ROOT', ''), settings.BASE_DIR / 'static']:
        if public and root.is_relative_to(Path(public).resolve()):
            raise BackupError('Backup directory must be outside media and static directories.')
    root.mkdir(parents=True, exist_ok=True)
    return root


def _database():
    config = connections['default'].settings_dict
    engine = config['ENGINE'].rsplit('.', 1)[-1]
    if engine not in {'sqlite3', 'postgresql', 'postgresql_psycopg2'}:
        raise BackupError('Only SQLite and PostgreSQL backups are supported.')
    if engine == 'sqlite3' and (not config['NAME'] or str(config['NAME']) == ':memory:' or str(config['NAME']).startswith('file:memory')):
        raise BackupError('Backups require a file-backed SQLite database.')
    return config, engine


def _identity(config):
    return sha256(json.dumps([str(config['NAME']), config.get('HOST', ''), str(config.get('PORT', ''))]).encode()).hexdigest()


def _schema():
    return sorted(f'{app}.{name}' for app, name in MigrationRecorder(connections['default']).applied_migrations())


def _digest(path):
    digest = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _pg_environment(config):
    env = os.environ.copy()
    for setting, name in [('USER', 'PGUSER'), ('PASSWORD', 'PGPASSWORD'), ('HOST', 'PGHOST'), ('PORT', 'PGPORT')]:
        env[name] = str(config.get(setting) or '')
    for option, value in config.get('OPTIONS', {}).items():
        if option in {'sslmode', 'sslrootcert', 'sslcert', 'sslkey'}:
            env['PG' + option.upper()] = str(value)
    return env


def _run_pg(args, config):
    try:
        subprocess.run(args, env=_pg_environment(config), check=True, capture_output=True, timeout=900, shell=False)
    except (OSError, subprocess.SubprocessError):
        # CLI output can contain credentials or provider connection details.
        raise BackupError('Database utility failed. Check the server database tooling and connection configuration.') from None


def _audit(action, actor, **details):
    event = {'time': timezone.now().isoformat(), 'action': action, 'actor': str(actor), **details}
    path = backup_directory() / 'operations.jsonl'
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event) + '\n')
    path.chmod(0o600)


@contextmanager
def operation_lock():
    root = backup_directory()
    lock = root / '.operation.lock'
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise BackupError('Another backup or restore is running. Try again when it finishes.') from None
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(str(os.getpid()))
        yield root
    finally:
        lock.unlink(missing_ok=True)


def create_backup(actor='scheduler', reason='manual'):
    if not settings.DB_BACKUP_ENABLED:
        raise BackupError('Database backups are disabled in this environment.')
    if configuration_problem():
        update_email_status('not_configured')
        raise BackupError('Configure SMTP email delivery before creating offsite backups. IT has been notified.')
    recipients = _email_recipients()
    config, engine = _database()
    with operation_lock() as root:
        identifier = uuid4().hex
        path = root / (identifier + ('.sqlite3' if engine == 'sqlite3' else '.dump'))
        try:
            if engine == 'sqlite3':
                source_path = Path(config['NAME']).resolve()
                with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(path)) as destination:
                    source.backup(destination)
                    if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise BackupError('SQLite integrity check failed.')
            else:
                _run_pg([settings.PG_DUMP_BIN, '--format=custom', '--no-owner', '--no-acl', '--file', str(path), '--dbname', str(config['NAME'])], config)
            path.chmod(0o600)
            record = {'id': identifier, 'filename': path.name, 'engine': engine, 'created_at': timezone.now().isoformat(),
                      'bytes': path.stat().st_size, 'sha256': _digest(path), 'database': _identity(config), 'migrations': _schema(), 'salary_key_ids': _salary_key_ids(), 'actor': str(actor), 'reason': reason}
            _email_archive(record, path, recipients)
            record['email_status'] = 'Captured by local test mailbox' if settings.DB_BACKUP_ALLOW_TEST_EMAIL else 'Accepted by mail server'
            record['recipient_count'] = len(recipients)
            manifest = root / (identifier + '.json')
            manifest.write_text(json.dumps(record), encoding='utf-8')
            manifest.chmod(0o600)
            _record_snapshot(record)
            _audit('backup_emailed', actor, backup=identifier, reason=reason, recipient_count=len(recipients))
            if not settings.DB_BACKUP_KEEP_LOCAL:
                path.unlink()
            return record
        except Exception as exc:
            path.unlink(missing_ok=True)
            (root / (identifier + '.json')).unlink(missing_ok=True)
            if isinstance(exc, sqlite3.Error):
                raise BackupError('SQLite backup failed. Check database access and integrity.') from None
            raise


def get_backup(identifier, verify=False):
    try:
        if UUID(identifier).hex != identifier:
            raise ValueError
        root = backup_directory()
        record = json.loads((root / (identifier + '.json')).read_text(encoding='utf-8'))
        suffix = '.sqlite3' if record['engine'] == 'sqlite3' else '.dump'
        if record['filename'] != identifier + suffix or record['id'] != identifier:
            raise ValueError
        path = root / record['filename']
        if not path.is_file():
            raise ValueError
        if verify and _digest(path) != record['sha256']:
            raise BackupError('Backup checksum does not match. Restore was refused.')
        return record, path
    except (OSError, ValueError, KeyError, TypeError):
        raise BackupError('Backup not found or its manifest is invalid.') from None


def list_backups():
    root = backup_directory()
    candidates = list(_snapshot_records())
    for manifest in root.glob('*.json'):
        try:
            candidates.append(json.loads(manifest.read_text(encoding='utf-8')))
        except (OSError, ValueError):
            continue
    records = {}
    for record in candidates:
        try:
            identifier = record['id']
            if UUID(identifier).hex != identifier or record['filename'] not in {identifier + '.sqlite3', identifier + '.dump'}:
                continue
            record['available_locally'] = (root / record['filename']).is_file()
            records[identifier] = record
        except (ValueError, KeyError, TypeError):
            continue
    return sorted(records.values(), key=lambda item: item['created_at'], reverse=True)


def restore_backup(identifier, actor, confirmation):
    if not (settings.DB_BACKUP_ENABLED and settings.DB_RESTORE_ENABLED and settings.DB_MAINTENANCE_MODE):
        raise BackupError('Restore requires backups, restore permission and maintenance mode enabled by the deployment operator.')
    if confirmation != 'RESTORE ' + identifier:
        raise BackupError('Type the exact restore confirmation shown for the selected snapshot.')
    config, engine = _database()
    record, path = get_backup(identifier, verify=True)
    _check_salary_keys(record)
    if record['engine'] != engine or not _database_matches(record, config) or record['migrations'] != _schema():
        raise BackupError('Backup database, engine or migration version does not match this environment.')
    # A fresh safety snapshot is mandatory before any destructive restore.
    safety = create_backup(actor, reason='pre-restore safety snapshot')
    with operation_lock():
        _audit('restore_started', actor, backup=identifier, safety=safety['id'])
        connections.close_all()
        try:
            if engine == 'sqlite3':
                with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source:
                    if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise BackupError('Backup integrity check failed.')
                    with closing(sqlite3.connect(str(config['NAME']))) as destination:
                        source.backup(destination)
            else:
                _run_pg([settings.PG_RESTORE_BIN, '--clean', '--if-exists', '--single-transaction', '--no-owner', '--no-acl', '--exit-on-error', '--dbname', str(config['NAME']), str(path)], config)
        except Exception:
            _audit('restore_failed', actor, backup=identifier, safety=safety['id'])
            raise
        finally:
            connections.close_all()
        _after_restore()
        _audit('restore_completed', actor, backup=identifier, safety=safety['id'])
        if not settings.DB_BACKUP_KEEP_LOCAL:
            path.unlink(missing_ok=True)
    return safety


def next_backup_run(frequency, run_at, weekday, now=None):
    local = timezone.localtime(now or timezone.now())
    if frequency == 'hourly':
        return local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    candidate = local.replace(hour=run_at.hour, minute=run_at.minute, second=0, microsecond=0)
    if frequency == 'weekly':
        candidate += timedelta(days=(weekday - candidate.weekday()) % 7)
        if candidate <= local:
            candidate += timedelta(days=7)
    elif frequency == 'daily':
        if candidate <= local:
            candidate += timedelta(days=1)
    else:
        raise BackupError('Unknown backup frequency.')
    return candidate


def _after_restore():
    # Do not silently reactivate an old schedule or resurrect old login sessions.
    from django.contrib.sessions.models import Session
    from .models import BackupSchedule
    BackupSchedule.objects.update(enabled=False, next_run=None, worker_heartbeat=None)
    Session.objects.all().delete()


def _email_recipients():
    from .models import BackupSchedule
    schedule = BackupSchedule.objects.filter(key='database').first()
    if schedule is None:
        raise BackupError('Configure backup email recipients in IT Operations first.')
    addresses = set()
    for address in schedule.recipients.filter(is_active=True).values_list('email', flat=True):
        try:
            validate_email(address)
        except ValidationError:
            raise BackupError('Every selected backup recipient must have a valid email address.') from None
        addresses.add(address)
    if not addresses:
        raise BackupError('Select at least one active backup email recipient in IT Operations.')
    return sorted(addresses)


def _email_archive(record, path, recipients):
    test_backend = settings.EMAIL_BACKEND in {
        'django.core.mail.backends.locmem.EmailBackend', 'django.core.mail.backends.filebased.EmailBackend',
        'django.core.mail.backends.console.EmailBackend', 'django.core.mail.backends.dummy.EmailBackend',
    }
    if test_backend and not (settings.DEBUG and settings.DB_BACKUP_ALLOW_TEST_EMAIL and settings.EMAIL_BACKEND in {
        'django.core.mail.backends.locmem.EmailBackend', 'django.core.mail.backends.filebased.EmailBackend',
    }):
        raise BackupError('Configure SMTP email delivery before creating offsite backups.')
    if path.stat().st_size > settings.DB_BACKUP_MAX_EMAIL_BYTES:
        raise BackupError('Backup exceeds the configured email attachment size limit. No email backup was created.')
    payload = archive_payload(record, path)
    if len(payload) > settings.DB_BACKUP_MAX_EMAIL_BYTES:
        raise BackupError('Backup archive exceeds the configured email attachment limit.')
    message = EmailMessage(
        subject='Database backup ' + record['id'],
        body=('Attached is the database recovery archive captured at ' + record['created_at'] + '. '
              'It contains sensitive application and account data. Keep it in an approved private mailbox. '
              'To recover, an IT operator imports this archive in IT Operations and confirms the restore. '
              'Uploaded media and Blob objects are not included.'),
        from_email=settings.DEFAULT_FROM_EMAIL, bcc=recipients,
    )
    message.attach('database-backup-' + record['id'] + '.zip', payload, 'application/zip')
    try:
        sent = message.send(fail_silently=False)
    except Exception:
        update_email_status('failed')
        raise BackupError('Backup email was not accepted. Check email delivery configuration; no completed backup is recorded.') from None
    if sent != 1:
        update_email_status('failed')
        raise BackupError('Backup email was not accepted; no completed backup is recorded.')
    update_email_status('accepted' if not settings.DB_BACKUP_ALLOW_TEST_EMAIL else 'unverified')


def import_backup_archive(upload, actor):
    if not settings.DB_BACKUP_ENABLED:
        raise BackupError('Backups are disabled in this environment.')
    limit = settings.DB_BACKUP_MAX_EMAIL_BYTES
    if upload.size > limit:
        raise BackupError('Recovery archive exceeds the configured size limit.')
    try:
        with zipfile.ZipFile(upload) as archive:
            if len(archive.infolist()) != 2 or archive.getinfo('manifest.json').file_size > 65536:
                raise BackupError('Recovery archive must contain one manifest and one database snapshot.')
            record = json.loads(archive.read('manifest.json'))
            identifier = record['id']
            if UUID(identifier).hex != identifier or record['filename'] not in {identifier + '.sqlite3', identifier + '.dump'}:
                raise BackupError('Invalid recovery manifest.')
            if set(archive.namelist()) != {'manifest.json', record['filename']}:
                raise BackupError('Unexpected files in recovery archive.')
            if archive.getinfo(record['filename']).file_size > limit:
                raise BackupError('Unpacked database exceeds the configured size limit.')
            payload = archive.read(record['filename'])
            if len(payload) != record['bytes'] or sha256(payload).hexdigest() != record['sha256']:
                raise BackupError('Recovery archive checksum or size does not match.')
        _check_salary_keys(record)
        config, engine = _database()
        expected_filename = identifier + ('.sqlite3' if engine == 'sqlite3' else '.dump')
        if record['filename'] != expected_filename or record['engine'] != engine or not _database_matches(record, config) or record['migrations'] != _schema():
            raise BackupError('Recovery archive does not match this database and migration version.')
        with operation_lock() as root:
            path = root / record['filename']
            path.write_bytes(payload)
            path.chmod(0o600)
            record.update(reason='imported emailed recovery archive', actor=str(actor))
            manifest = root / (identifier + '.json')
            manifest.write_text(json.dumps(record), encoding='utf-8')
            manifest.chmod(0o600)
            _record_snapshot(record)
            _audit('emailed_backup_imported', actor, backup=identifier)
        return record
    except (zipfile.BadZipFile, OSError, KeyError, ValueError, TypeError, RuntimeError):
        raise BackupError('Recovery archive is invalid or unreadable.') from None


def _database_matches(record, config):
    if record['database'] == _identity(config):
        return True
    return (settings.DB_RESTORE_ALLOW_DIFFERENT_DATABASE and settings.DB_RESTORE_ENABLED
            and settings.DB_MAINTENANCE_MODE)


def archive_payload(record, path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', json.dumps(record))
        archive.write(path, arcname=record['filename'])
    return stream.getvalue()


def _record_snapshot(record):
    from .models import BackupSnapshot
    BackupSnapshot.objects.update_or_create(identifier=record['id'], defaults={'metadata': record})


def _snapshot_records():
    from .models import BackupSnapshot
    return BackupSnapshot.objects.values_list('metadata', flat=True)


def _salary_key_ids():
    return [sha256(key.encode() if isinstance(key, str) else key).hexdigest() for key in settings.SALARY_ENCRYPTION_KEYS]


def _check_salary_keys(record):
    if not set(record.get('salary_key_ids', [])) <= set(_salary_key_ids()):
        raise BackupError('Salary encryption keys required by this archive are not configured. Restore was refused.')
