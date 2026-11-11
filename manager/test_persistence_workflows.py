import json
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from adminpanel.models import ResearchCentre
from manager.models import Book, BookComment, Chapter, DashboardTask
from projects.models import Project
from users.navigation import workspace_base


class PersistentWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.centre = ResearchCentre.objects.create(name='Persistence centre')
        cls.other_centre = ResearchCentre.objects.create(name='Outside persistence centre')
        cls.users = {role: User.objects.create_user('saved-' + role, role=role, research_centre=cls.centre) for role, _ in User.ROLE_CHOICES}
        cls.users['staff_superuser'] = User.objects.create_user('saved-elevated-staff', role='staff', is_superuser=True, research_centre=cls.centre)
        cls.project = Project.objects.create(name='Saved publication project', project_type='book', created_by=cls.users['manager'], assigned_user=cls.users['financialadmin'], research_centre=cls.centre)
        cls.book = Book.objects.create(title='Saved book', lead_author='Lead', created_by=cls.users['manager'], project=cls.project, total_chapters=4)
        cls.outside_user = User.objects.create_user('outside-author', role='manager', research_centre=cls.other_centre)
        cls.outside_book = Book.objects.create(title='Outside book', lead_author='Outside', created_by=cls.outside_user)

    def post_json(self, route, data, args=None, client=None):
        return (client or self.client).post(reverse(route, args=args), json.dumps(data), content_type='application/json')

    def chapter_payload(self, number=1, **kwargs):
        return {'chapter_number': number, 'title': 'Saved chapter', 'assigned_author_id': self.users['staff'].pk, 'author': '', 'editor': 'Editor', 'status': 'Draft', **kwargs}

    def test_chapter_create_edit_delete_and_reload_for_every_role(self):
        report = {}
        for index, (role, user) in enumerate(self.users.items(), start=1):
            self.client.force_login(user)
            editable = role in {'admin', 'manager', 'centrehead', 'overseer', 'staff_superuser'}
            with self.subTest(role=role):
                response = self.post_json('add_chapter', self.chapter_payload(index), [self.book.pk])
                self.assertEqual(response.status_code, 200 if editable else 403)
                if editable:
                    chapter_id = response.json()['id']
                    chapter = Chapter.objects.get(pk=chapter_id)
                    self.assertEqual(chapter.assigned_author, self.users['staff'])
                    reloaded = self.client.get(reverse('get_chapters', args=[self.book.pk])).json()
                    self.assertIn(chapter_id, [item['id'] for item in reloaded['chapters']])
                    edited = self.post_json('edit_chapter', self.chapter_payload(index, title='Saved edit ' + role, status='Completed'), [chapter_id])
                    self.assertEqual(edited.status_code, 200)
                    chapter.refresh_from_db()
                    self.assertEqual((chapter.title, chapter.status), ('Saved edit ' + role, 'Completed'))
                    self.book.refresh_from_db()
                    self.assertEqual(self.book.completed_chapters, 1)
                    self.assertContains(self.client.get(reverse('admin_book')), 'Saved edit ' + role)
                    self.assertEqual(self.post_json('delete_chapter', {}, [chapter_id]).status_code, 200)
                    self.assertFalse(Chapter.objects.filter(pk=chapter_id).exists())
                    self.book.refresh_from_db()
                    self.assertEqual(self.book.completed_chapters, 0)
                report[role] = {'chapter_changes': 'saved, edited, deleted and reloaded' if editable else '403; existing permission boundary preserved'}
        path = Path(settings.BASE_DIR) / 'test_artifacts' / 'persistence_role_api_results.json'
        path.write_text(json.dumps(report, indent=2) + '\n')

    def test_author_can_read_only_assigned_chapters_and_cannot_forge_updates(self):
        own = Chapter.objects.create(book=self.book, chapter_number=1, title='Own chapter', assigned_author=self.users['staff'], author='Staff')
        private = Chapter.objects.create(book=self.book, chapter_number=2, title='Another author chapter', assigned_author=self.users['supervisor'], author='Supervisor')
        self.client.force_login(self.users['staff'])
        self.assertEqual([row['id'] for row in self.client.get(reverse('get_chapters', args=[self.book.pk])).json()['chapters']], [own.pk])
        self.assertNotContains(self.client.get(reverse('manager_book')), private.title)
        self.assertEqual(self.post_json('edit_chapter', self.chapter_payload(1), [own.pk]).status_code, 403)
        self.assertEqual(self.post_json('delete_chapter', {}, [own.pk]).status_code, 403)

    def test_chapter_validation_is_atomic_and_keeps_book_progress(self):
        self.client.force_login(self.users['manager'])
        good = self.post_json('add_chapter', self.chapter_payload(), [self.book.pk])
        self.assertEqual(good.status_code, 200)
        for values in [{'chapter_number': 0}, {'chapter_number': ''}, {'title': ''}, {'status': 'invented'}, {'assigned_author_id': self.outside_user.pk}, {'chapter_number': 1}]:
            with self.subTest(values=values):
                self.assertEqual(self.post_json('add_chapter', self.chapter_payload(**values), [self.book.pk]).status_code, 400)
        self.assertEqual(Chapter.objects.filter(book=self.book).count(), 1)
        self.assertEqual(self.client.post(reverse('add_chapter', args=[self.book.pk]), '[', content_type='application/json').status_code, 400)
        self.assertEqual(self.post_json('add_chapter', self.chapter_payload(), [self.outside_book.pk]).status_code, 404)
        self.assertEqual(self.client.get(reverse('delete_chapter', args=[good.json()['id']])).status_code, 405)

    def test_external_author_names_can_be_saved_without_creating_an_account(self):
        self.client.force_login(self.users['manager'])
        response = self.post_json('add_chapter', self.chapter_payload(author='External researcher', assigned_author_id=''), [self.book.pk])
        self.assertEqual(response.status_code, 200)
        chapter = Chapter.objects.get(pk=response.json()['id'])
        self.assertEqual(chapter.author, 'External researcher')
        self.assertIsNone(chapter.assigned_author_id)

    def test_book_comments_save_reload_and_share_across_permitted_roles(self):
        for role, user in self.users.items():
            self.client.force_login(user)
            allowed = role not in {'it', 'student'}
            with self.subTest(role=role):
                response = self.post_json('book_comments', {'text': 'Persisted discussion ' + role, 'user_id': self.users['admin'].pk}, [self.book.pk])
                self.assertEqual(response.status_code, 200 if allowed else 404)
                if allowed:
                    saved = BookComment.objects.get(text='Persisted discussion ' + role)
                    self.assertEqual(saved.user, user)
                    refreshed = self.client.get(reverse('book_comments', args=[self.book.pk])).json()['comments']
                    self.assertIn(saved.pk, [row['id'] for row in refreshed])
        self.client.force_login(self.users['admin'])
        self.assertEqual(len(self.client.get(reverse('book_comments', args=[self.book.pk])).json()['comments']), 9)

    def test_comments_reject_empty_too_long_foreign_and_unassigned_finance(self):
        self.client.force_login(self.users['manager'])
        for text in ['', '  ', 'x' * 10001]:
            self.assertEqual(self.post_json('book_comments', {'text': text}, [self.book.pk]).status_code, 400)
        self.assertEqual(self.post_json('book_comments', {'text': 'Private'}, [self.outside_book.pk]).status_code, 404)
        self.client.force_login(self.users['financialadmin'])
        self.project.assigned_user = self.users['manager']; self.project.save()
        self.assertEqual(self.post_json('book_comments', {'text': 'Not assigned'}, [self.book.pk]).status_code, 404)
        self.assertEqual(BookComment.objects.count(), 0)

    def test_personal_tasks_create_complete_reopen_delete_and_reload_for_every_role(self):
        for role, user in self.users.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                self.assertEqual(self.post_json('dashboard_tasks', {'title': 'Today task ' + role, 'user_id': self.users['admin'].pk}).status_code, 200)
                task = DashboardTask.objects.get(user=user, title='Today task ' + role)
                fresh = self.client.get(reverse('dashboard_tasks')).json()['tasks']
                self.assertEqual([row['id'] for row in fresh], [task.pk])
                for action, completed in [('complete', True), ('reopen', False)]:
                    self.assertEqual(self.post_json('dashboard_task_update', {'action': action}, [task.pk]).status_code, 200)
                    self.assertEqual(self.client.get(reverse('dashboard_tasks')).json()['tasks'][0]['completed'], completed)
                page = self.client.get(reverse('manager_dashboard'))
                self.assertTemplateUsed(page, workspace_base(user))
                self.assertEqual(self.post_json('dashboard_task_update', {'action': 'delete'}, [task.pk]).status_code, 200)
                self.assertEqual(self.client.get(reverse('dashboard_tasks')).json()['tasks'], [])

    def test_personal_task_isolation_validation_and_date_filter(self):
        user = self.users['manager']
        task = DashboardTask.objects.create(user=user, title='Private task')
        old = DashboardTask.objects.create(user=user, title='Yesterday', work_date=timezone.localdate() - timedelta(days=1))
        self.client.force_login(self.users['staff'])
        self.assertEqual(self.client.get(reverse('dashboard_tasks')).json()['tasks'], [])
        self.assertEqual(self.post_json('dashboard_task_update', {'action': 'delete'}, [task.pk]).status_code, 404)
        for title in ['', ' ', 'x' * 256]:
            self.assertEqual(self.post_json('dashboard_tasks', {'title': title}).status_code, 400)
        self.client.force_login(user)
        self.assertEqual([row['id'] for row in self.client.get(reverse('dashboard_tasks')).json()['tasks']], [task.pk])
        self.assertTrue(DashboardTask.objects.filter(pk=old.pk).exists())
        self.assertEqual(self.post_json('dashboard_task_update', {'action': 'unexpected'}, [task.pk]).status_code, 400)
        self.assertEqual(self.client.get(reverse('dashboard_task_update', args=[task.pk])).status_code, 405)

    def test_fresh_browser_csrf_is_required_and_supported_for_all_new_saves(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.users['manager'])
        client.get(reverse('manager_dashboard'))
        token = client.cookies['csrftoken'].value
        for route, payload, args in [('dashboard_tasks', {'title': 'Protected'}, None), ('add_chapter', self.chapter_payload(), [self.book.pk]), ('book_comments', {'text': 'Protected comment'}, [self.book.pk])]:
            with self.subTest(route=route):
                self.assertEqual(self.post_json(route, payload, args, client).status_code, 403)
                response = client.post(reverse(route, args=args), json.dumps(payload), content_type='application/json', HTTP_X_CSRFTOKEN=token)
                self.assertEqual(response.status_code, 200)

    def test_confirmed_legacy_import_is_atomic_private_and_repeatable(self):
        self.client.force_login(self.users['manager'])
        payload = {'import_tasks': [{'text': 'Old browser work', 'completed': True}]}
        for _ in range(2):
            self.assertEqual(self.post_json('dashboard_tasks', payload).status_code, 200)
        task = DashboardTask.objects.get(user=self.users['manager'], title='Old browser work')
        self.assertTrue(task.completed)
        bad = {'import_tasks': [{'text': 'Must not partially save'}, {'text': ''}]}
        self.assertEqual(self.post_json('dashboard_tasks', bad).status_code, 400)
        self.assertFalse(DashboardTask.objects.filter(title='Must not partially save').exists())
        self.client.force_login(self.users['staff'])
        self.assertEqual(self.client.get(reverse('dashboard_tasks')).json()['tasks'], [])
