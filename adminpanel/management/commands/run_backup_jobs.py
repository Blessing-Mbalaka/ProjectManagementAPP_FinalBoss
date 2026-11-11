"""Run managed backups from a worker or from a system cron invocation."""
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from adminpanel.models import BackupSchedule
from adminpanel.backup_service import BackupError, backup_directory, create_backup, next_backup_run


class Command(BaseCommand):
    help = 'Run due database backup jobs once (cron) or continuously (--loop).'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')

    def handle(self, *args, **options):
        while True:
            self.run_due()
            if not options['loop']:
                break
            time.sleep(30)

    def run_due(self):
        from django.conf import settings
        if not settings.DB_BACKUP_ENABLED:
            self.stdout.write('Database backups are disabled; no jobs executed.')
            return
        now = timezone.now()
        (backup_directory() / 'worker-heartbeat').write_text(now.isoformat())
        heartbeat, _ = BackupSchedule.objects.get_or_create(key='database')
        BackupSchedule.objects.filter(pk=heartbeat.pk).update(worker_heartbeat=now)
        for job in BackupSchedule.objects.filter(enabled=True, next_run__lte=now):
            following = next_backup_run(job.frequency, job.run_at, job.weekday, now)
            # Compare and update claims the due run across competing workers.
            claimed = BackupSchedule.objects.filter(pk=job.pk, enabled=True, next_run=job.next_run).update(next_run=following, last_run=now)
            if not claimed:
                continue
            try:
                record = create_backup('scheduler', reason='scheduled backup')
                result = 'Completed: ' + record['id']
            except (BackupError, OSError):
                result = 'Failed: check backup storage, database tooling and concurrent operations.'
            BackupSchedule.objects.filter(pk=job.pk).update(last_result=result)
            self.stdout.write(result)
