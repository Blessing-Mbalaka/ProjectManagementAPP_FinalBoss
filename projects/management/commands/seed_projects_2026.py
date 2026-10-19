"""Apply reviewed 2026 allocations through the existing workbook importer."""
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from projects.models import Project
from projects.seed_batch import apply_seed_batch
from projects.workbook_import.schema import WorkbookReadResult
from projects.workbook_import.validation import validate_workbook


class Command(BaseCommand):
    help = 'Validate or seed reviewed 2026 project allocations; apply requires a database backup.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write records (default is a read-only preview).')
        parser.add_argument('--backup-dir', help='Private directory for a complete pre-import database backup.')
        parser.add_argument('--pg-dump', default='pg_dump', help='PostgreSQL pg_dump executable.')

    def handle(self, *args, **options):
        path = Path(settings.BASE_DIR) / 'projects' / 'seed_data' / 'projects_2026.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        actor = get_user_model().objects.get(username='thabile', is_active=True, role='admin')
        rows = tuple(dict(row, _row=i) for i, row in enumerate(data['projects'], 2))
        tasks = tuple(dict(row, _row=i) for i, row in enumerate(data['tasks'], 2))
        result = WorkbookReadResult(project_rows=rows, task_rows=tasks)
        preview = validate_workbook(result, actor=actor)
        for issue in preview.issues:
            self.stdout.write(f'{issue.level}: {issue.sheet} {issue.row} {issue.field}: {issue.message}')
        if preview.errors or preview.warnings:
            raise CommandError('Resolve all import issues before seeding.')
        adoptions = self._adoptions(data)
        self.stdout.write(f'Validated {len(rows)} projects, {len(tasks)} tasks; {len(adoptions)} existing project(s) to adopt.')
        if not options['apply']:
            self.stdout.write('Preview only. No records written.')
            return
        if not options['backup_dir']:
            raise CommandError('--backup-dir is required with --apply.')
        backup = self._backup(options)
        self.stdout.write(f'Database backup: {backup}')
        with transaction.atomic():
            # Lock and revalidate adoption targets before giving them stable import identities.
            adoptions = self._adoptions(data, lock=True)
            for project_id, key in adoptions:
                Project.objects.filter(pk=project_id).update(import_key=key)
            imported = apply_seed_batch(preview, actor=actor)
            project_ids = imported.affected_project_ids
            if len(project_ids) != len(rows):
                raise CommandError('Project reconciliation failed; transaction rolled back.')
            from projects.models import Task
            expected = {(r.project_import_key, r.import_key, r.assigned_to_id, r.parent_normalized) for r in preview.tasks}
            from projects.workbook_import.validation import normalize_name
            actual = {
                (t.project.import_key, t.import_key, t.assigned_to_id, normalize_name(t.parent_task.title) if t.parent_task else '')
                for t in Task.objects.filter(project_id__in=project_ids, import_key__in=[r.import_key for r in preview.tasks]).select_related('project', 'parent_task')
            }
            if actual != expected:
                raise CommandError('Task allocation reconciliation failed; transaction rolled back.')
        self.stdout.write(self.style.SUCCESS(
            f'Projects created: {imported.created_projects}; updated: {imported.updated_projects}; '
            f'tasks created: {imported.created_tasks}; updated: {imported.updated_tasks}. Allocations reconciled.'
        ))

    def _adoptions(self, data, lock=False):
        keys = {r['project_name']: r['import_key'] for r in data['projects']}
        pending = []
        for name, pk in data['existing_projects'].items():
            query = Project.objects.select_for_update() if lock else Project.objects
            project = query.filter(pk=pk).first()
            if project is None or project.name != name or project.project_type != 'software':
                raise CommandError(f'Existing project {pk} does not match reviewed adoption {name!r}.')
            if project.import_key == keys[name]:
                continue
            if project.import_key:
                raise CommandError(f'{name} already has a different import identity.')
            if Project.objects.filter(import_key=keys[name]).exists():
                raise CommandError(f'{name} would duplicate an existing seeded project.')
            pending.append((pk, keys[name]))
        # Never silently duplicate a pre-existing project with an exact title.
        adopted_ids = set(data['existing_projects'].values())
        for row in data['projects']:
            conflicts = Project.objects.filter(name__iexact=row['project_name']).exclude(import_key=row['import_key']).exclude(pk__in=adopted_ids)
            if conflicts.exists():
                raise CommandError(f'Existing title requires an explicit adoption decision: {row["project_name"]}')
        return pending

    def _backup(self, options):
        directory = Path(options['backup_dir']).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        if connection.vendor == 'sqlite':
            import sqlite3
            path = directory / f'pre-projects-2026-{stamp}.sqlite3'
            connection.ensure_connection()
            with sqlite3.connect(path) as target:
                connection.connection.backup(target)
            return path
        if connection.vendor != 'postgresql':
            raise CommandError('Backup is supported only for PostgreSQL or SQLite.')
        path = directory / f'pre-projects-2026-{stamp}.dump'
        db = connection.settings_dict
        env = os.environ.copy()
        env['PGPASSWORD'] = str(db.get('PASSWORD') or '')
        env['PGCONNECT_TIMEOUT'] = '30'
        command = [options['pg_dump'], '--format=custom', '--no-password', '--file', str(path),
                   '--host', str(db['HOST']), '--port', str(db.get('PORT') or 5432),
                   '--username', str(db['USER']), str(db['NAME'])]
        try:
            subprocess.run(command, env=env, check=True, capture_output=True, timeout=180)
        except (OSError, subprocess.SubprocessError) as exc:
            raise CommandError('Database backup failed; no seed changes were applied.') from exc
        if not path.exists() or path.stat().st_size < 5 or path.open('rb').read(5) != b'PGDMP':
            raise CommandError('Database backup is invalid; no seed changes were applied.')
        return path
