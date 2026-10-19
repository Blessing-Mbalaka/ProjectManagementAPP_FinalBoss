import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from adminpanel.models import ResearchCentre
from manager.models import Book, Paper
from projects.models import Project, Task
from django.db import transaction, connection
from django.test.utils import CaptureQueriesContext
from projects.workbook_import.schema import WorkbookReadResult
from projects.workbook_import.validation import validate_workbook
from projects.workbook_import.application import apply_workbook_preview
from projects.seed_batch import apply_seed_batch


class SeedProjects2026Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = json.loads((Path(settings.BASE_DIR) / 'projects/seed_data/projects_2026.json').read_text(encoding='utf-8'))
        centre = ResearchCentre.objects.create(name='Centre for digital Transformation')
        usernames = {p['username'] for p in cls.data['personnel'] if p['username']} | {'raksha'}
        for username in usernames:
            get_user_model().objects.create_user(username=username, role='admin' if username == 'thabile' else 'staff', research_centre=centre)
        Project.objects.create(id=8, name='Project Management App', project_type='software')

    def test_preview_does_not_write(self):
        call_command('seed_projects_2026', stdout=StringIO())
        self.assertEqual(Project.objects.count(), 1)
        self.assertFalse(Task.objects.exists())
        self.assertIsNone(Project.objects.get(pk=8).import_key)

    def test_backup_failure_prevents_all_changes(self):
        with patch('projects.management.commands.seed_projects_2026.Command._backup', side_effect=CommandError('backup failed')):
            with self.assertRaises(CommandError):
                call_command('seed_projects_2026', apply=True, backup_dir='unused', stdout=StringIO())
        self.assertEqual(Project.objects.count(), 1)
        self.assertFalse(Task.objects.exists())
        self.assertIsNone(Project.objects.get(pk=8).import_key)

    def test_seed_is_idempotent_and_preserves_allocations(self):
        with patch('projects.management.commands.seed_projects_2026.Command._backup', return_value=Path('test-backup.dump')):
            call_command('seed_projects_2026', apply=True, backup_dir='unused', stdout=StringIO())
            first = list(Task.objects.order_by('pk').values_list('pk', 'assigned_to_id', 'parent_task_id'))
            call_command('seed_projects_2026', apply=True, backup_dir='unused', stdout=StringIO())
        self.assertEqual(Project.objects.count(), 71)
        self.assertEqual(Task.objects.count(), 131)
        self.assertEqual(list(Task.objects.order_by('pk').values_list('pk', 'assigned_to_id', 'parent_task_id')), first)
        self.assertTrue(Project.objects.get(pk=8).import_key.startswith('allocations-2026:'))
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(Paper.objects.count(), 29)
        book = Project.objects.get(name='Digitalization for Dummies')
        self.assertEqual(book.tasks.filter(parent_task__isnull=True).count(), 12)
        self.assertTrue(book.tasks.filter(assigned_to__username='BlessingMbalaka', parent_task__isnull=False).exists())
        self.assertTrue(Task.objects.filter(project__name='From ESG Reporting to ESG Intelligence', assigned_to__username='andile').exists())

    def test_unreviewed_existing_title_blocks_seed(self):
        Project.objects.create(name='Horizon', project_type='software')
        with self.assertRaisesMessage(CommandError, 'explicit adoption'):
            call_command('seed_projects_2026', stdout=StringIO())

    def test_batch_matches_workbook_importer_with_bounded_database_round_trips(self):
        actor = get_user_model().objects.get(username='thabile')
        key = next(p['import_key'] for p in self.data['projects'] if p['project_name']=='Project Management App')
        Project.objects.filter(pk=8).update(import_key=key)
        preview = validate_workbook(WorkbookReadResult(project_rows=tuple(dict(r,_row=i) for i,r in enumerate(self.data['projects'],2)),task_rows=tuple(dict(r,_row=i) for i,r in enumerate(self.data['tasks'],2))),actor=actor)
        self.assertFalse(preview.issues)
        def snapshot():
            from projects.models import Assignment
            return {
                'projects': sorted(Project.objects.values_list('import_key','name','description','portfolio','project_type','status','due_date','assigned_user_id','research_centre_id','created_by_id')),
                'tasks': sorted(Task.objects.values_list('project__import_key','title','assigned_to_id','parent_task__title','status','progress','comments','priority','task_type','due_date')),
                'papers': sorted((p.title,p.status,p.paper_type,p.internal_external,p.version,p.lead_author_user_id,tuple(p.co_authors_users.order_by('username').values_list('username',flat=True))) for p in Paper.objects.all()),
                'books': sorted((p.title,p.status,p.total_chapters,p.completed_chapters,p.lead_author_user_id,tuple(p.co_authors_users.order_by('username').values_list('username',flat=True))) for p in Book.objects.all()),
                'memberships': sorted(Assignment.objects.values_list('project__import_key','team_member__user__username')),
            }
        with transaction.atomic():
            apply_workbook_preview(preview,actor=actor)
            expected=snapshot()
            transaction.set_rollback(True)
        with CaptureQueriesContext(connection) as queries:
            apply_seed_batch(preview,actor=actor)
        self.assertLess(len(queries),60)
        self.assertEqual(snapshot(),expected)
