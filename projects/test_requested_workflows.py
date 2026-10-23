import json
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from adminpanel.models import ClockInRecord, ResearchCentre
from manager.models import Book, Chapter
from projects.models import Project, Task, WeeklyReport
from projects.work_scope import manageable_projects_for, workable_tasks_for
from users.roles import has_role


class RequestedRoleAndPrivacyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.centre = ResearchCentre.objects.create(name='Centre A')
        self.other_centre = ResearchCentre.objects.create(name='Centre B')
        self.staff = User.objects.create_user('raksha', password='pass', role='staff', research_centre=self.centre)
        self.other_staff = User.objects.create_user('other', password='pass', role='staff', research_centre=self.centre)
        self.manager = User.objects.create_user('pm', password='pass', role='manager', research_centre=self.centre)
        self.head = User.objects.create_user('head', password='pass', role='centrehead', research_centre=self.centre)
        self.finance = User.objects.create_user('finance', password='pass', role='financialadmin', research_centre=self.centre)
        self.other_head = User.objects.create_user('other-head', password='pass', role='centrehead', research_centre=self.other_centre)
        self.thabile = User.objects.create_superuser('thabile', password='pass', role='admin', research_centre=self.centre)
        self.thabile.groups.add(Group.objects.create(name='project_manager'))
        self.project = Project.objects.create(name='Book delivery', project_type='book', created_by=self.manager, assigned_user=self.staff, research_centre=self.centre)
        self.other_project = Project.objects.create(name='Other centre', created_by=self.other_head, research_centre=self.other_centre)

    def test_staff_only_sees_own_tasks(self):
        mine = Task.objects.create(project=self.project, title='Mine', assigned_to=self.staff, created_by=self.manager)
        Task.objects.create(project=self.project, title='Someone else', assigned_to=self.other_staff, created_by=self.manager)
        self.assertEqual(list(workable_tasks_for(self.staff)), [mine])

    def test_centre_head_and_finance_manage_only_their_centre(self):
        self.assertIn(self.project, manageable_projects_for(self.head))
        self.assertNotIn(self.other_project, manageable_projects_for(self.head))
        self.assertIn(self.project, manageable_projects_for(self.finance))
        self.assertNotIn(self.other_project, manageable_projects_for(self.finance))

    def test_manager_superuser_has_both_entitlements_without_multi_role_schema(self):
        self.assertTrue(has_role(self.thabile, 'manager'))
        self.assertTrue(has_role(self.thabile, 'admin'))

    def test_financial_admin_can_create_centre_project(self):
        self.client.force_login(self.finance)
        response = self.client.post(reverse('create_project'), {
            'name': 'Client onboarding', 'description': 'Lead follow-up',
            'project_type': 'software', 'status': 'planning', 'due_date': '2026-12-01',
        })
        self.assertEqual(response.status_code, 302)
        created = Project.objects.get(name='Client onboarding')
        self.assertEqual(created.research_centre, self.centre)

    def test_centre_head_can_allocate_centre_project(self):
        self.client.force_login(self.head)
        response = self.client.post(reverse('admin_assign_project'), {
            'project_id': self.project.id, 'assigned_user': self.other_staff.id,
        })
        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.assigned_user, self.other_staff)

    def test_centre_head_pm_tools_open_full_centre_project_workspace(self):
        self.client.force_login(self.head)

        overview = self.client.get(reverse('overview'))
        workspace = self.client.get(
            reverse('assign_projects'),
            {'project_id': self.project.id},
        )

        self.assertContains(overview, 'Manage &amp; Load Projects')
        self.assertContains(overview, reverse('assign_projects'))
        self.assertContains(overview, 'backdrop-filter:none')
        self.assertEqual(workspace.status_code, 200)
        self.assertContains(workspace, 'Centre Project Management')
        self.assertContains(workspace, 'Upload Workbook')
        self.assertContains(workspace, 'New Project')
        self.assertContains(workspace, 'Assign Project Lead')
        self.assertContains(workspace, self.project.name)
        self.assertNotContains(workspace, self.other_project.name)

    def test_centre_head_can_add_tasks_to_any_project_in_own_centre_only(self):
        self.client.force_login(self.head)
        response = self.client.post(reverse('manager_create_task', args=[self.project.id]), {
            'title': 'Centre head milestone',
            'status': 'todo',
            'task_type': 'Book',
            'priority': 'High',
            'assigned_to': '',
            'parent_task': '',
            'due_date': '',
        })

        self.assertRedirects(
            response,
            f"{reverse('assign_projects')}?project_id={self.project.id}",
        )
        self.assertTrue(Task.objects.filter(
            project=self.project,
            title='Centre head milestone',
            created_by=self.head,
        ).exists())
        outside_response = self.client.post(
            reverse('manager_create_task', args=[self.other_project.id]),
            {'title': 'Forbidden outside task', 'status': 'todo'},
        )
        self.assertEqual(outside_response.status_code, 404)

    def test_centre_head_project_lead_assignment_returns_to_workspace(self):
        self.client.force_login(self.head)
        response = self.client.post(reverse('admin_assign_project'), {
            'project_id': self.project.id,
            'assigned_user': self.other_staff.id,
            'return_to': 'project_workspace',
        })

        self.assertRedirects(
            response,
            f"{reverse('assign_projects')}?project_id={self.project.id}",
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.assigned_user, self.other_staff)

    def test_centre_head_sidebar_exposes_scoped_research_project_tools(self):
        self.client.force_login(self.head)

        overview = self.client.get(reverse('overview'))

        self.assertContains(overview, 'Research Projects')
        self.assertContains(overview, 'Book Projects')
        self.assertContains(overview, 'Paper Projects')
        self.assertContains(overview, 'Conferences')
        self.assertEqual(self.client.get(reverse('admin_book')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin_journal')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin_conferences')).status_code, 200)

    def test_book_project_created_in_assignment_workspace_gets_book_tracker(self):
        self.client.force_login(self.head)

        response = self.client.post(reverse('create_project'), {
            'name': 'Centre Handbook',
            'description': 'A practical centre handbook',
            'project_type': 'book',
            'status': 'planning',
            'due_date': '2027-06-30',
            'book_lead_author': 'Lead Writer',
            'book_total_chapters': '12',
        })

        self.assertRedirects(response, reverse('assign_projects'))
        project = Project.objects.get(name='Centre Handbook')
        book = Book.objects.get(project=project)
        self.assertEqual(project.project_type, 'book')
        self.assertEqual(project.research_centre, self.centre)
        self.assertEqual(book.lead_author, 'Lead Writer')
        self.assertEqual(book.total_chapters, 12)

    def test_standalone_book_creation_also_creates_linked_book_project(self):
        self.client.force_login(self.head)

        response = self.client.post(
            reverse('add_book'),
            json.dumps({
                'title': 'Research Methods Book',
                'lead_author': 'Centre Author',
                'description': 'Methods reference',
                'status': 'writing',
                'total_chapters': 8,
                'completed_chapters': 0,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        book = Book.objects.get(title='Research Methods Book')
        self.assertIsNotNone(book.project)
        self.assertEqual(book.project.project_type, 'book')
        self.assertEqual(book.project.research_centre, self.centre)

    def test_financial_admin_can_open_client_engagement_workspace(self):
        self.client.force_login(self.finance)
        self.assertEqual(self.client.get(reverse('manager_engagements')).status_code, 200)


class ChapterPrivacyAndBulkAssignmentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.centre = ResearchCentre.objects.create(name='Books Centre')
        self.manager = User.objects.create_user('manager', password='pass', role='manager', research_centre=self.centre)
        self.author = User.objects.create_user('author', password='pass', role='staff', research_centre=self.centre)
        self.other_author = User.objects.create_user('author2', password='pass', role='staff', research_centre=self.centre)
        self.book = Book.objects.create(title='Secure Book', lead_author='Lead', created_by=self.manager, total_chapters=2)
        self.own = Chapter.objects.create(book=self.book, chapter_number=1, title='Own', author='Author', assigned_author=self.author)
        Chapter.objects.create(book=self.book, chapter_number=2, title='Private', author='Other', assigned_author=self.other_author)

    def test_author_endpoint_returns_only_assigned_chapter(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('get_chapters', args=[self.book.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['title'] for item in response.json()['chapters']], ['Own'])

    def test_bulk_assignment_updates_author_and_is_idempotent(self):
        self.client.force_login(self.manager)
        payload = {'chapters': [{'chapter_number': 1, 'title': 'Reassigned', 'assigned_author_id': self.other_author.id, 'status': 'In Progress'}]}
        url = reverse('bulk_assign_chapters', args=[self.book.id])
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post(url, json.dumps(payload), content_type='application/json').status_code, 200)
        self.own.refresh_from_db()
        self.assertEqual(self.own.assigned_author, self.other_author)
        self.assertEqual(Chapter.objects.filter(book=self.book, chapter_number=1).count(), 1)


class WeeklyReportAndClockTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.centre = ResearchCentre.objects.create(name='Reporting Centre')
        self.staff = User.objects.create_user('staff', password='pass', role='staff', research_centre=self.centre)
        self.head = User.objects.create_user('head', password='pass', role='centrehead', research_centre=self.centre)
        self.project = Project.objects.create(name='Paper project', project_type='paper', assigned_user=self.staff, research_centre=self.centre)
        Task.objects.create(project=self.project, title='Staff task', assigned_to=self.staff)

    def test_weekly_report_snapshots_project_type_and_updates_same_week(self):
        self.client.force_login(self.staff)
        url = reverse('weekly_reports')
        data = {'project': self.project.id, 'week_start': '2026-10-19', 'summary': 'First'}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        data['summary'] = 'Updated'
        self.client.post(url, data)
        report = WeeklyReport.objects.get()
        self.assertEqual(report.project_type, 'paper')
        self.assertEqual(report.summary, 'Updated')

    def test_clock_in_location_is_optional_and_requires_explicit_consent(self):
        self.client.force_login(self.staff)
        url = reverse('clock_in')
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, json.dumps({
            'location_consent': True, 'latitude': -26.2041, 'longitude': 28.0473, 'accuracy': 25,
        }), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        record = ClockInRecord.objects.get()
        self.assertIsNotNone(record.location_consent_at)
        self.assertEqual(record.location_accuracy_m, 25)

    def test_centre_head_activity_cannot_select_other_centre_employee(self):
        other = get_user_model().objects.create_user('outside', password='pass', role='staff')
        ClockInRecord.objects.create(employee=other, clock_in_time='2026-10-23T08:00:00Z')
        self.client.force_login(self.head)
        response = self.client.get(reverse('user_activity_api'), {'employee_id': other.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['recent_records'], [])


class PublicationAndGanttTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.centre = ResearchCentre.objects.create(name='Publication Centre')
        self.staff = User.objects.create_user('raksha', password='pass', role='staff', research_centre=self.centre)
        self.student = User.objects.create_user('student', password='pass', role='student', research_centre=self.centre)
        self.head = User.objects.create_user('head', password='pass', role='centrehead', research_centre=self.centre)

    def test_staff_author_can_open_classified_publication_upload(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('manager_journal'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'paper_type')

    def test_student_cannot_open_publication_management(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('manager_journal')).status_code, 403)

    def test_large_gantt_defaults_to_one_row_per_project(self):
        projects = [Project(name=f'P{i}', research_centre=self.centre, created_by=self.head) for i in range(150)]
        Project.objects.bulk_create(projects)
        self.client.force_login(self.head)
        response = self.client.get(reverse('admin_ganttchart'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'P149')
        self.assertEqual(len(response.context['projects']), 150)
        self.assertContains(response, 'Back to Overview')
        self.assertContains(response, 'Fit Screen')
        self.assertContains(response, 'toggleGanttSidebar')
        self.assertContains(response, 'fitGanttToWidth')
        self.assertContains(response, 'headerLabelStep')
        self.assertContains(response, 'day-label-muted')
