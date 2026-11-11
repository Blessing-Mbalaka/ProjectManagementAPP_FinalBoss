import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse

from adminpanel.models import CostCentre, Notification, ResearchCentre
from adminpanel.notification_service import unread_count_for
from projects.models import ChatMessage, Meeting, Project, StudentProfile, Task
from users.navigation import role_home_name, workspace_base


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.links = set()
        self.forms = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        in_sidebar = any('sidebar' in classes or 'sidebar-menu' in classes for _, classes in self.stack)
        if tag == 'a' and in_sidebar:
            self.links.add(attrs.get('href', ''))
        if tag == 'form':
            self.forms.append({'action': attrs.get('action', ''), 'method': attrs.get('method', 'get').lower()})
        if tag not in {'img', 'input', 'br', 'hr', 'meta', 'link', 'source', 'wbr'}:
            self.stack.append((tag, attrs.get('class', '').split()))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}, DB_BACKUP_DIR=settings.BASE_DIR / 'test_artifacts' / 'navigation_backups', DB_BACKUP_ENABLED=False, DB_BACKUP_ALLOW_TEST_EMAIL=True)
class GlobalNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.centre = ResearchCentre.objects.create(name='Navigation evaluation centre')
        cls.profiles = {role: users.objects.create_user('navigation-' + role, role=role, research_centre=cls.centre) for role, _ in users.ROLE_CHOICES}
        cls.profiles['staff_superuser'] = users.objects.create_user('navigation-staff-superuser', role='staff', research_centre=cls.centre, is_superuser=True)
        CostCentre.objects.create(name='Navigation cost centre', code='NAV-001', research_centre=cls.centre)
        StudentProfile.objects.create(user=cls.profiles['student'], supervisor=cls.profiles['supervisor'], program='Research', year='2026', research_title='Navigation test')
        cls.projects = {}
        for label, user in cls.profiles.items():
            cls.projects[label] = Project.objects.create(name='Navigation assigned ' + label, created_by=cls.profiles['manager'], assigned_user=user, research_centre=cls.centre, project_type='financial' if label == 'financialadmin' else 'software')

    def test_staff_superuser_saves_to_own_task_page_and_keeps_staff_navigation(self):
        user = self.profiles['staff_superuser']
        project = self.projects['staff_superuser']
        self.client.force_login(user)
        response = self.client.post(reverse('add_task', args=[project.pk]), {'title': 'Elevated staff self task', 'status': 'todo', 'assigned_to': user.pk})
        self.assertRedirects(response, reverse('project_tasks', args=[project.pk]))
        page = self.client.get(response.url)
        self.assertTemplateUsed(page, 'base.html')
        self.assertEqual(page.context['project_tasks_back_url'], reverse('staff_projects'))
        self.assertTrue(get_user_model().objects.get(pk=user.pk).is_superuser)

    def test_task_creation_returns_to_origin_for_all_project_roles(self):
        for role in ['admin', 'centrehead', 'overseer', 'manager', 'financialadmin', 'staff', 'staff_superuser']:
            with self.subTest(role=role):
                user = self.profiles[role]; project = self.projects[role]
                self.client.force_login(user)
                origin = reverse('project_tasks', args=[project.pk])
                response = self.client.post(reverse('add_task', args=[project.pk]), {'title': 'Origin task ' + role, 'status': 'todo', 'assigned_to': user.pk, 'return_to': origin})
                self.assertRedirects(response, origin)
                self.assertTemplateUsed(self.client.get(origin), workspace_base(user))

    def test_bad_task_form_stays_in_project_workspace_for_staff_and_elevated_staff(self):
        for role in ['staff', 'staff_superuser', 'manager', 'financialadmin']:
            with self.subTest(role=role):
                user = self.profiles[role]; project = self.projects[role]
                self.client.force_login(user)
                origin = reverse('project_tasks', args=[project.pk])
                page = self.client.post(reverse('add_task', args=[project.pk]), {'title': '', 'status': 'todo', 'assigned_to': user.pk, 'return_to': origin})
                self.assertEqual(page.status_code, 200)
                self.assertTemplateUsed(page, 'projects/project_tasks.html')
                self.assertTemplateUsed(page, workspace_base(user))
                self.assertContains(page, 'This field is required.')

    def test_kanban_add_and_delete_preserve_admin_assignee_filter(self):
        user = self.profiles['admin']; project = self.projects['admin']
        self.client.force_login(user)
        origin = reverse('financial_kanban') + f'?assignee={user.pk}'
        response = self.client.post(reverse('add_task', args=[project.pk]), {'title': 'Filtered board task', 'status': 'todo', 'assigned_to': user.pk, 'return_to': origin})
        self.assertRedirects(response, origin)
        task = Task.objects.get(title='Filtered board task')
        self.assertRedirects(self.client.post(reverse('manager_delete_task', args=[task.pk]), {'return_to': origin}), origin)
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())

    def test_kanban_validation_keeps_the_board_instead_of_assignment_dashboard(self):
        user = self.profiles['financialadmin']; project = self.projects['financialadmin']
        self.client.force_login(user)
        origin = reverse('financial_kanban')
        page = self.client.post(reverse('add_task', args=[project.pk]), {'title': '', 'status': 'todo', 'return_to': origin})
        self.assertTemplateUsed(page, 'manager/manager_kanban.html')
        self.assertTemplateUsed(page, 'adminpanel/index.html')
        self.assertTrue(page.context['open_task_modal'])
        self.assertEqual(page.context['task_return_url'], origin)

    def test_external_wrong_feature_and_other_project_return_urls_are_rejected(self):
        user = self.profiles['staff']; project = self.projects['staff']
        self.client.force_login(user)
        fallback = reverse('project_tasks', args=[project.pk])
        for target in ['https://example.invalid/collect', '//example.invalid/collect', reverse('overview'), reverse('it_dashboard'), reverse('project_tasks', args=[self.projects['manager'].pk])]:
            with self.subTest(target=target):
                response = self.client.post(reverse('add_task', args=[project.pk]), {'title': 'Safe return ' + target, 'status': 'todo', 'assigned_to': user.pk, 'return_to': target})
                self.assertEqual(response.url, fallback)

    def test_same_origin_referer_is_supported_for_existing_forms(self):
        user = self.profiles['manager']; project = self.projects['manager']
        self.client.force_login(user)
        origin = reverse('project_tasks', args=[project.pk])
        response = self.client.post(reverse('add_task', args=[project.pk]), {'title': 'Referer return task', 'status': 'todo'}, HTTP_REFERER='http://testserver' + origin)
        self.assertEqual(response.url, origin)

    def test_shared_communique_remains_shared_and_returns_to_each_roles_home(self):
        for role, user in self.profiles.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                page = self.client.get(reverse('communique'))
                self.assertEqual(page.status_code, 200)
                self.assertEqual(page.context['communique_back_url'], reverse(role_home_name(user)))
                for section in ['templates', 'messages', 'availability']:
                    page = self.client.get(reverse('communique_section', args=[section]))
                    self.assertEqual(page.status_code, 200)
                    self.assertEqual(page.context['communique_back_url'], reverse('communique'))

    def test_communique_upload_errors_stay_on_templates_section(self):
        self.client.force_login(self.profiles['admin'])
        origin = reverse('communique_section', args=['templates'])
        self.assertRedirects(self.client.post(reverse('upload_communique_template'), {'template_name': 'No file', 'return_to': origin}), origin)

    def test_unknown_shared_section_cannot_be_a_return_target(self):
        self.client.force_login(self.profiles['admin'])
        origin = reverse('communique_section', args=['missing-section'])
        self.assertRedirects(self.client.post(reverse('upload_communique_template'), {'return_to': origin}, HTTP_REFERER='http://testserver' + origin), reverse('communique_section', args=['templates']))

    def test_paper_save_keeps_admin_and_pm_in_their_publication_workspaces(self):
        for role, route in [('admin', 'admin_journal'), ('manager', 'manager_journal')]:
            self.client.force_login(self.profiles[role])
            origin = reverse(route)
            response = self.client.post(reverse('add_paper'), {'paperTitle': 'Role-aware paper ' + role, 'paperStatus': 'draft', 'paperType': 'internal', 'currentVersion': '1.0', 'leadAuthor': role, 'coAuthors': '', 'targetJournal': 'Journal', 'paperAbstract': 'Navigation evaluation', 'return_to': origin})
            self.assertRedirects(response, origin)

    def test_supervisor_wrong_role_fallback_is_not_admin_dashboard(self):
        self.client.force_login(self.profiles['staff'])
        self.assertRedirects(self.client.get(reverse('supervisor_dashboard_portal')), reverse('dashboard'))

    def test_staff_cannot_be_returned_into_finance_readonly(self):
        for role in ['staff', 'staff_superuser', 'student', 'it']:
            self.client.force_login(self.profiles[role])
            response = self.client.get(reverse('finance_readonly'))
            if response.status_code == 302:
                self.assertEqual(response.url, reverse(role_home_name(self.profiles[role])))
            else:
                self.assertEqual(response.status_code, 403)

    def test_task_edit_and_invalid_edit_return_to_same_board(self):
        for role in ['admin', 'centrehead', 'overseer', 'manager', 'financialadmin', 'staff', 'staff_superuser']:
            with self.subTest(role=role):
                user = self.profiles[role]
                project = self.projects[role]
                task = Task.objects.create(project=project, title='Editable ' + role, assigned_to=user, created_by=user)
                self.client.force_login(user)
                origin = reverse('project_tasks', args=[project.pk])
                route = 'staff_edit_task' if role in {'staff', 'staff_superuser'} else 'edit_task'
                payload = {'title': 'Updated ' + role, 'status': 'in_progress', 'project': project.pk, 'return_to': origin}
                self.assertRedirects(self.client.post(reverse(route, args=[task.pk]), payload), origin)
                task.refresh_from_db()
                self.assertEqual(task.status, 'in_progress')
                self.assertEqual(task.progress, 33)
                payload['status'] = 'invalid'
                self.assertRedirects(self.client.post(reverse(route, args=[task.pk]), payload), origin)
                task.refresh_from_db()
                self.assertEqual(task.status, 'in_progress')

    def test_invalid_assignment_preserves_workspace_and_bound_errors(self):
        for role in ['admin', 'manager', 'financialadmin', 'staff_superuser']:
            with self.subTest(role=role):
                self.client.force_login(self.profiles[role])
                page = self.client.post(reverse('assign_team_member', args=[self.projects[role].pk]), {})
                self.assertEqual(page.status_code, 200)
                self.assertTrue(page.context['assignment_form'].errors)
                self.assertEqual(page.context['project'], self.projects[role])
                self.assertTrue(page.context['workspace_title'])
                expected = reverse('financial_projects') if role == 'financialadmin' else reverse(role_home_name(self.profiles[role]))
                self.assertEqual(page.context['workspace_back_url'], expected)

    def test_shared_resource_pages_keep_primary_role_navigation(self):
        for role in ['admin', 'manager', 'supervisor', 'financialadmin', 'staff_superuser']:
            self.client.force_login(self.profiles[role])
            for route in ['manager_journal', 'manager_templates', 'manager_elearning', 'staff_templates', 'staff_elearning']:
                with self.subTest(role=role, route=route):
                    page = self.client.get(reverse(route))
                    if role == 'financialadmin' and route == 'manager_journal':
                        self.assertEqual(page.status_code, 403)
                    else:
                        self.assertEqual(page.status_code, 200)
                        self.assertTemplateUsed(page, workspace_base(self.profiles[role]))

    def test_filtered_financial_board_validation_preserves_selected_assignee(self):
        user = self.profiles['admin']
        self.client.force_login(user)
        origin = reverse('financial_kanban') + f'?assignee={user.pk}'
        page = self.client.post(reverse('add_task', args=[self.projects['admin'].pk]), {'title': '', 'return_to': origin})
        self.assertEqual(page.context['selected_assignee'], str(user.pk))
        self.assertEqual(page.context['task_return_url'], origin)

    def test_student_notification_button_marks_role_and_global_notices_read(self):
        student = self.profiles['student']
        self.client.force_login(student)
        for audience in ['all', 'role']:
            notification = Notification.objects.create(title='Student notice', body='Notification body', audience=audience, audience_role='student' if audience == 'role' else None, created_by=self.profiles['admin'])
            page = self.client.get(reverse('student_dashboard'))
            action = reverse('student_mark_notification_read', args=[notification.pk])
            self.assertContains(page, action)
            self.assertContains(page, 'Notification body')
            self.assertRedirects(self.client.post(action), reverse('student_dashboard') + '#notifications-section')
        self.assertEqual(unread_count_for(student), 0)
        self.assertEqual(self.client.get(action).status_code, 405)
        hidden = Notification.objects.create(title='Private', body='Admin only', audience='role', audience_role='admin', created_by=self.profiles['admin'])
        self.assertEqual(self.client.post(reverse('student_mark_notification_read', args=[hidden.pk])).status_code, 404)

    def test_student_meeting_and_chat_return_to_student_portal(self):
        student = self.profiles['student']
        self.client.force_login(student)
        self.assertRedirects(self.client.post(reverse('submit_meeting'), {'date': '2026-11-20', 'time': '10:00', 'duration': 30, 'purpose': 'Review work', 'mode': 'Virtual'}), reverse('student_dashboard'))
        self.assertTrue(Meeting.objects.filter(student=student).exists())
        self.assertRedirects(self.client.post(reverse('send_chat'), {'message': 'Student progress update'}), reverse('student_dashboard'))
        self.assertTrue(ChatMessage.objects.filter(sender=student, recipient=self.profiles['supervisor']).exists())

    def test_finance_validation_preserves_section_and_query(self):
        for role in ['admin', 'financialadmin', 'centrehead']:
            self.client.force_login(self.profiles[role])
            origin = reverse('finance_section', args=['payments']) + '?search=NAV-001'
            response = self.client.post(reverse('add_payment'), {'return_to': origin})
            self.assertEqual(response.url, origin)

    def test_dean_does_not_get_publication_buttons_the_role_cannot_use(self):
        from manager.models import Paper
        Paper.objects.create(title='Dean oversight paper', created_by=self.profiles['admin'], lead_author='Author', internal_external='internal')
        self.client.force_login(self.profiles['dean'])
        journal = self.client.get(reverse('admin_journal'))
        self.assertContains(journal, 'Dean oversight paper')
        self.assertNotContains(journal, 'btn btn-sm btn-warning editBtn')
        self.assertNotContains(self.client.get(reverse('admin_book')), 'id="addNewBookBtn"')
        self.assertEqual(self.client.post(reverse('add_paper'), {}).status_code, 403)

    def test_shared_messaging_actions_work_for_every_staff_role_including_it(self):
        for role, user in self.profiles.items():
            if role == 'student':
                continue
            with self.subTest(role=role):
                self.client.force_login(user)
                recipient = self.profiles['staff'] if role == 'admin' else self.profiles['admin']
                response = self.client.post(reverse('api_send_staff_message'), json.dumps({'recipient_id': recipient.pk, 'message': 'Role navigation shared action ' + role}), content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['success'])
                self.assertNotIn('Location', response)
                self.assertTrue(ChatMessage.objects.filter(sender=user, recipient=recipient, message='Role navigation shared action ' + role).exists())

    def test_student_shared_messages_offer_working_supervisor_chat(self):
        self.client.force_login(self.profiles['student'])
        page = self.client.get(reverse('communique_section', args=['messages']))
        self.assertContains(page, reverse('student_dashboard') + '#chat-section')
        self.assertNotContains(page, 'id="newMessageBtn"')
        self.assertEqual(self.client.get(reverse('api_recipients_list')).status_code, 403)

    def test_shared_page_sets_csrf_cookie_for_non_admin_ajax_saves(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.profiles['it'])
        client.get(reverse('communique_section', args=['messages']))
        self.assertIn('csrftoken', client.cookies)
        response = client.post(reverse('api_send_staff_message'), json.dumps({'recipient_id': self.profiles['admin'].pk, 'message': 'CSRF protected shared save'}), content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_shared_availability_saves_for_all_roles_without_leaving_section(self):
        from adminpanel.models import UserAvailability
        for role, user in self.profiles.items():
            with self.subTest(role=role):
                self.client.force_login(user)
                response = self.client.post(reverse('api_update_availability'), json.dumps({'date': '2026-11-20', 'status': 'available'}), content_type='application/json')
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['success'])
                self.assertNotIn('Location', response)
                self.assertTrue(UserAvailability.objects.filter(user=user, date='2026-11-20', status='available').exists())

    def test_visible_role_navigation_and_rendered_form_actions_resolve(self):
        report = {}
        for role, user in self.profiles.items():
            self.client.force_login(user)
            home = reverse(role_home_name(user))
            response = self.client.get(home, follow=True)
            self.assertEqual(response.status_code, 200, role)
            parser = NavigationParser(); parser.feed(response.content.decode())
            urls = {url for url in parser.links if url.startswith('/') and resolve(urlsplit(url).path).url_name not in {'logout', 'clock_out', 'clock_in'}}
            urls.update({home, reverse('communique')})
            urls.update(reverse('communique_section', args=[section]) for section in ['templates', 'messages', 'availability'])
            if role in {'admin', 'centrehead', 'overseer', 'manager', 'financialadmin', 'staff', 'staff_superuser'}:
                urls.add(reverse('project_tasks', args=[self.projects[role].pk]))
            rows = []
            for url in sorted(urls):
                with self.subTest(role=role, url=url):
                    page = self.client.get(url, follow=True)
                    self.assertEqual(page.status_code, 200, (role, url, page.redirect_chain))
                    self.assertEqual(page.request['PATH_INFO'], urlsplit(url).path, (role, url, page.redirect_chain))
                    action_count = 0
                    if page.get('Content-Type', '').startswith('text/html'):
                        buttons = NavigationParser(); buttons.feed(page.content.decode())
                        for form in buttons.forms:
                            action = urlsplit(form['action']).path or urlsplit(url).path
                            if action.startswith('/'):
                                resolve(action)
                                action_count += 1
                    rows.append({'page': url, 'final_page': page.request['PATH_INFO'], 'status': page.status_code, 'resolved_form_actions': action_count})
            report[role] = rows
        path = Path(settings.BASE_DIR) / 'test_artifacts' / 'global_role_navigation_audit.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
