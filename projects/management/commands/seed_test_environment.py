"""Seed a disposable, file-backed SQLite environment for UI and load testing."""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from adminpanel.models import ResearchCentre
from manager.models import Book, Chapter
from projects.models import Assignment, Project, Task, TeamMember


class Command(BaseCommand):
    help = 'Seed dummy users and many projects; refuses to run outside settings_test/test.db.'

    def add_arguments(self, parser):
        parser.add_argument('--projects', type=int, default=200)

    @transaction.atomic
    def handle(self, *args, **options):
        database_name = Path(str(settings.DATABASES['default']['NAME'])).resolve()
        expected = Path(settings.TEST_DB_PATH).resolve() if hasattr(settings, 'TEST_DB_PATH') else None
        if expected is None or database_name != expected or database_name.name != 'test.db':
            raise CommandError('Refusing to seed: use --settings=project_manage.settings_test with test_artifacts/test.db.')

        count = max(1, min(options['projects'], 2000))
        centre, _ = ResearchCentre.objects.get_or_create(name='Codex Test Centre')
        User = get_user_model()
        specs = [
            ('demo-centre-head', 'centrehead', False),
            ('demo-pm', 'manager', False),
            ('demo-finance', 'financialadmin', False),
            ('demo-raksha', 'staff', False),
            ('demo-prof', 'staff', False),
            ('demo-thabile', 'admin', True),
        ]
        users = {}
        for username, role, is_superuser in specs:
            user, _ = User.objects.get_or_create(username=username, defaults={'role': role})
            user.role = role
            user.research_centre = centre
            user.is_staff = is_superuser
            user.is_superuser = is_superuser
            user.set_password('DemoPass!2026')
            user.save()
            users[username] = user
        manager_group, _ = Group.objects.get_or_create(name='project_manager')
        users['demo-thabile'].groups.add(manager_group)

        today = timezone.localdate()
        projects = []
        for index in range(count):
            project, _ = Project.objects.update_or_create(
                import_key=f'codex-test:{index}',
                defaults={
                    'name': f'Demo Project {index + 1:04d}',
                    'description': 'Disposable load-test record',
                    'project_type': ('book', 'paper', 'conference', 'software')[index % 4],
                    'status': ('planning', 'in-progress', 'on-hold', 'completed')[index % 4],
                    'created_by': users['demo-pm'],
                    'assigned_user': users['demo-raksha'] if index % 2 == 0 else users['demo-prof'],
                    'research_centre': centre,
                    'due_date': today + timedelta(days=7 + index % 180),
                },
            )
            projects.append(project)
        for project in projects:
            for task_index in range(3):
                Task.objects.update_or_create(
                    project=project,
                    import_key=f'demo-task:{task_index}',
                    defaults={
                        'title': f'{project.name} task {task_index + 1}',
                        'assigned_to': project.assigned_user,
                        'created_by': users['demo-pm'],
                        'status': ('todo', 'in_progress', 'review')[task_index],
                        'due_date': project.due_date - timedelta(days=2 - task_index),
                    },
                )

        # A recognizable multi-author book reproduces the former leakage case:
        # one manager tracker plus separate, explicitly assigned author work.
        book_project, _ = Project.objects.update_or_create(
            import_key='codex-test:book-privacy',
            defaults={
                'name': 'Digitalization for Dummies (Demo)',
                'description': 'Safe demonstration of chapter and personal Kanban isolation.',
                'project_type': 'book',
                'status': 'in-progress',
                'created_by': users['demo-pm'],
                'assigned_user': users['demo-pm'],
                'research_centre': centre,
                'due_date': today + timedelta(days=90),
            },
        )
        for username, responsibility in (
            ('demo-raksha', 'Responsible author: Digital Readiness'),
            ('demo-prof', 'Responsible author: Digital Governance'),
        ):
            user = users[username]
            member, _ = TeamMember.objects.update_or_create(
                user=user,
                defaults={'full_name': user.get_full_name() or user.username, 'role': 'Author'},
            )
            Assignment.objects.update_or_create(
                project=book_project,
                team_member=member,
                defaults={'responsibility': responsibility},
            )

        book, _ = Book.objects.update_or_create(
            project=book_project,
            defaults={
                'title': 'Digitalization for Dummies (Demo)',
                'description': 'Dummy book used only in the isolated SQLite environment.',
                'lead_author': users['demo-pm'].username,
                'lead_author_user': users['demo-pm'],
                'total_chapters': 2,
                'completed_chapters': 0,
                'created_by': users['demo-pm'],
                'due_date': book_project.due_date,
            },
        )
        book.co_authors_users.set([users['demo-raksha'], users['demo-prof']])
        chapter_specs = (
            (1, 'Digital Readiness', users['demo-raksha']),
            (2, 'Digital Governance', users['demo-prof']),
        )
        for number, title, author in chapter_specs:
            Chapter.objects.update_or_create(
                book=book,
                chapter_number=number,
                defaults={
                    'title': title,
                    'author': author.username,
                    'assigned_author': author,
                    'status': 'In Progress',
                },
            )
        task_specs = (
            ('book-manager-tracker', 'Chapter: manager-only tracker', None),
            ('book-raksha', 'Write Digital Readiness — demo-raksha', users['demo-raksha']),
            ('book-prof', 'Write Digital Governance — demo-prof', users['demo-prof']),
        )
        for import_key, title, assignee in task_specs:
            Task.objects.update_or_create(
                project=book_project,
                import_key=import_key,
                defaults={
                    'title': title,
                    'assigned_to': assignee,
                    'created_by': users['demo-pm'],
                    'status': 'in_progress',
                    'due_date': book_project.due_date - timedelta(days=14),
                },
            )

        seeded_projects = Project.objects.filter(import_key__startswith='codex-test:').count()
        seeded_tasks = Task.objects.filter(project__import_key__startswith='codex-test:').count()
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(users)} dummy users, {seeded_projects} projects and {seeded_tasks} tasks in {database_name}.'
        ))
