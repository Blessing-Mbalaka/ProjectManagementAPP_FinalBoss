import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from adminpanel.models import EngagementLog, FinancialProject, ResearchCentre
from projects.models import Project, Task, TeamMember


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class FinancialWorkspaceTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name='Workspace Centre')
        users = get_user_model()
        self.finance = users.objects.create_user('workspace-finance', role='financialadmin', research_centre=self.centre)
        self.manager = users.objects.create_user('workspace-pm', role='manager', research_centre=self.centre)
        self.other = users.objects.create_user('workspace-other', role='financialadmin', research_centre=self.centre)
        self.project = Project.objects.create(name='Assigned client opportunity', project_type='financial', research_centre=self.centre, assigned_user=self.finance, created_by=self.finance)
        self.record = FinancialProject.objects.create(project=self.project, owner=self.finance, research_centre=self.centre, client_name='Workspace Client')
        self.task = Task.objects.create(project=self.project, title='Assigned finance work', assigned_to=self.finance, created_by=self.finance)
        self.client.force_login(self.finance)

    def engagement_data(self, project=None):
        return {'project': (project or self.project).pk, 'entry_type': 'discussion', 'contact_method': 'email', 'engagement_date': timezone.localdate().isoformat(), 'notes': 'Confirmed client requirements.', 'client_name': 'Workspace Client'}

    def test_finance_engagements_keep_finance_navigation_and_return_path(self):
        for route in ['financial_engagements', 'manager_engagements']:
            page = self.client.get(reverse(route))
            self.assertTemplateUsed(page, 'adminpanel/index.html')
            self.assertTemplateNotUsed(page, 'manager/home.html')
            self.assertContains(page, 'Back to Financial Projects')
            self.assertContains(page, 'Financial Workspace')
            self.assertContains(page, 'href="' + reverse('my_projects') + '"')
            self.assertNotContains(page, 'href="' + reverse('manager_dashboard') + '"')

    def test_finance_note_saves_and_redirects_with_financial_context(self):
        for route in ['manager_engagements', 'financial_engagements']:
            response = self.client.post(reverse(route), self.engagement_data())
            self.assertRedirects(response, reverse('financial_engagements') + f'?project={self.project.pk}')
        self.assertEqual(EngagementLog.objects.filter(project=self.project, entered_by=self.finance).count(), 2)

    def test_finance_note_rejects_unassigned_project(self):
        private = Project.objects.create(name='Private peer project', created_by=self.other, assigned_user=self.other, research_centre=self.centre)
        response = self.client.post(reverse('financial_engagements'), self.engagement_data(private))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EngagementLog.objects.filter(project=private).exists())

    def test_assignment_workspace_returns_to_finance_instead_of_pm_dashboard(self):
        page = self.client.get(reverse('assign_projects'))
        self.assertContains(page, 'Financial Project Management')
        self.assertContains(page, 'href="' + reverse('financial_projects') + '"')
        self.assertNotContains(page, 'href="' + reverse('manager_dashboard') + '"')

    def test_my_projects_includes_direct_task_assignment_without_exposing_peer_work(self):
        direct = Project.objects.create(name='Direct task allocation', created_by=self.other, assigned_user=self.other, research_centre=self.centre)
        mine = Task.objects.create(project=direct, title='My directly assigned task', assigned_to=self.finance, created_by=self.other)
        Task.objects.create(project=direct, title='Private peer task', assigned_to=self.other, created_by=self.other)
        page = self.client.get(reverse('my_projects'))
        self.assertContains(page, direct.name)
        self.assertContains(page, mine.title)
        self.assertNotContains(page, 'Private peer task')
        response = self.client.post(reverse('my_project_task_update', args=[mine.pk]), {'status': 'done', 'comments': 'Completed assigned work.'})
        self.assertRedirects(response, reverse('my_projects'))
        mine.refresh_from_db()
        self.assertEqual((mine.status, mine.progress, mine.comments), ('done', 100, 'Completed assigned work.'))

    def test_my_projects_cannot_update_peer_task_and_rejects_invalid_status(self):
        private = Project.objects.create(name='Private work', assigned_user=self.other, created_by=self.other, research_centre=self.centre)
        task = Task.objects.create(project=private, title='Peer work', assigned_to=self.other, created_by=self.other)
        self.assertEqual(self.client.post(reverse('my_project_task_update', args=[task.pk]), {'status': 'done'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('my_project_task_update', args=[self.task.pk]), {'status': 'invalid'}).status_code, 400)

    def test_new_bid_is_visible_in_kanban_and_saves_after_reload(self):
        response = self.client.post(reverse('add_financial_project'), {'project_name': 'New visible bid', 'client_name': 'New Kanban Client', 'contact_email': 'contact@example.test', 'applied_date': timezone.localdate().isoformat()})
        self.assertRedirects(response, reverse('financial_projects'))
        record = FinancialProject.objects.get(project__name='New visible bid')
        task = record.project.tasks.get()
        page = self.client.get(reverse('financial_kanban'))
        self.assertContains(page, task.title)
        self.assertTemplateUsed(page, 'adminpanel/index.html')
        self.assertIn(task, page.context['grouped_tasks']['todo'])
        self.assertEqual(page.context['kanban_average_progress'], 0)
        response = self.client.post(reverse('update_task_status', args=[task.pk]), json.dumps({'status': 'in_progress'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        page = self.client.get(reverse('financial_kanban'))
        self.assertIn(task, page.context['grouped_tasks']['in_progress'])
        task.refresh_from_db()
        self.assertEqual(task.progress, 33)
        self.assertEqual(page.context['kanban_average_progress'], 16.5)

    def test_task_only_assignment_does_not_show_misleading_empty_board_message(self):
        self.project.assigned_user = self.other
        self.project.created_by = self.other
        self.project.save()
        page = self.client.get(reverse('financial_kanban'))
        self.assertContains(page, self.task.title)
        self.assertNotContains(page, 'No projects have been assigned to you yet.')

    def test_admin_has_oversight_while_finance_board_excludes_unassigned_peer_work(self):
        project = Project.objects.create(name='Peer client bid', project_type='financial', created_by=self.other, assigned_user=self.other, research_centre=self.centre)
        task = Task.objects.create(project=project, title='Other financial owner follow-up', created_by=self.other, assigned_to=self.other)
        page = self.client.get(reverse('financial_kanban'))
        self.assertContains(page, self.task.title)
        self.assertNotContains(page, task.title)
        admin = get_user_model().objects.create_user('workspace-admin', role='admin')
        self.client.force_login(admin)
        page = self.client.get(reverse('financial_kanban'))
        self.assertContains(page, self.task.title)
        self.assertContains(page, task.title)

    def test_pm_keeps_pm_engagement_layout_and_has_my_projects(self):
        self.client.force_login(self.manager)
        page = self.client.get(reverse('manager_engagements'))
        self.assertTemplateUsed(page, 'manager/home.html')
        self.assertContains(page, 'href="' + reverse('my_projects') + '"')
        page = self.client.get(reverse('my_projects'))
        self.assertTemplateUsed(page, 'manager/home.html')

    def test_staff_cannot_enter_management_workspaces(self):
        staff = get_user_model().objects.create_user('workspace-staff', role='staff', research_centre=self.centre)
        self.client.force_login(staff)
        for route in ['my_projects', 'financial_engagements']:
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_admin_can_create_bid_for_financial_admin_starting_in_todo(self):
        admin = get_user_model().objects.create_user('assign-bid-admin', role='admin', research_centre=self.centre)
        self.client.force_login(admin)
        response = self.client.post(reverse('add_financial_project'), {'project_name': 'Delegated submitted bid', 'client_name': 'Delegated Client', 'contact_email': 'client@example.test', 'applied_date': timezone.localdate().isoformat(), 'owner_id': self.finance.pk})
        self.assertRedirects(response, reverse('financial_projects'))
        bid = FinancialProject.objects.get(project__name='Delegated submitted bid')
        task = bid.project.tasks.get(import_key='financial-bid-follow-up')
        self.assertEqual((bid.owner_id, bid.project.assigned_user_id, task.assigned_to_id), (self.finance.pk,) * 3)
        self.assertEqual((task.status, task.progress), ('todo', 0))
        self.client.force_login(self.finance)
        self.assertContains(self.client.get(reverse('financial_kanban')), task.title)
        self.assertContains(self.client.get(reverse('my_projects')), bid.project.name)

    def test_reassignment_resets_only_followup_and_repeating_assignment_preserves_progress(self):
        admin = get_user_model().objects.create_user('reassign-bid-admin', role='admin', research_centre=self.centre)
        self.task.title = 'Bid follow-up: Workspace Client'
        self.task.status = 'review'
        self.task.save()
        unrelated = Task.objects.create(project=self.project, title='Unrelated task must keep progress', assigned_to=self.finance, status='review')
        self.client.force_login(admin)
        response = self.client.post(reverse('assign_financial_project', args=[self.record.pk]), {'owner_id': self.other.pk})
        self.assertRedirects(response, reverse('financial_projects'))
        self.record.refresh_from_db(); self.project.refresh_from_db(); self.task.refresh_from_db(); unrelated.refresh_from_db()
        self.assertEqual((self.record.owner_id, self.project.assigned_user_id, self.task.assigned_to_id), (self.other.pk,) * 3)
        self.assertEqual((self.task.status, self.task.progress), ('todo', 0))
        self.assertEqual((unrelated.status, unrelated.progress, unrelated.assigned_to_id), ('review', 66, self.finance.pk))
        self.task.status = 'in_progress'; self.task.save()
        self.client.post(reverse('assign_financial_project', args=[self.record.pk]), {'owner_id': self.other.pk})
        self.task.refresh_from_db()
        self.assertEqual((self.task.status, self.task.progress), ('in_progress', 33))

    def test_financial_admin_cannot_delegate_to_peer_or_manipulate_creation_owner(self):
        self.assertEqual(self.client.post(reverse('assign_financial_project', args=[self.record.pk]), {'owner_id': self.other.pk}).status_code, 403)
        response = self.client.post(reverse('add_financial_project'), {'project_name': 'Forged delegation', 'client_name': 'Not allowed', 'contact_email': 'client@example.test', 'owner_id': self.other.pk})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Project.objects.filter(name='Forged delegation').exists())

    def test_admin_rejects_foreign_centre_and_inactive_financial_assignees(self):
        users = get_user_model()
        admin = users.objects.create_user('invalid-assignee-admin', role='admin', research_centre=self.centre)
        foreign_centre = ResearchCentre.objects.create(name='Other assignment centre')
        foreign = users.objects.create_user('foreign-financial-owner', role='financialadmin', research_centre=foreign_centre)
        inactive = users.objects.create_user('inactive-financial-owner', role='financialadmin', research_centre=self.centre, is_active=False)
        self.client.force_login(admin)
        for user in [foreign, inactive, self.manager]:
            self.assertEqual(self.client.post(reverse('assign_financial_project', args=[self.record.pk]), {'owner_id': user.pk}).status_code, 404)
        self.assertEqual(self.client.post(reverse('assign_financial_project', args=[self.record.pk]), {'owner_id': 'invalid'}).status_code, 400)

    def test_admin_can_filter_assignees_but_financial_admin_cannot_view_peers(self):
        project = Project.objects.create(name='Filtered peer bid', project_type='financial', assigned_user=self.other, created_by=self.other, research_centre=self.centre)
        peer_task = Task.objects.create(project=project, title='Filtered peer follow-up', assigned_to=self.other, created_by=self.other)
        admin = get_user_model().objects.create_user('filter-admin', role='admin')
        self.client.force_login(admin)
        page = self.client.get(reverse('financial_kanban'), {'assignee': self.finance.pk})
        self.assertContains(page, self.task.title)
        self.assertNotContains(page, peer_task.title)
        self.assertContains(page, 'All assignees')
        self.assertEqual(self.client.get(reverse('financial_kanban'), {'assignee': 'invalid'}).status_code, 400)
        self.client.force_login(self.finance)
        page = self.client.get(reverse('financial_kanban'), {'assignee': self.other.pk})
        self.assertNotContains(page, peer_task.title)
        self.assertNotContains(page, 'id="financialAssignee"')

    def test_pm_can_assign_every_project_type_to_finance_who_can_create_tasks_and_subtasks(self):
        member = TeamMember.objects.create(user=self.finance, full_name='Finance team member')
        for project_type, _label in Project.PROJECT_TYPES:
            for allocation in ['lead', 'team']:
                with self.subTest(project_type=project_type, allocation=allocation):
                    name = f'PM allocated {project_type} {allocation}'
                    self.client.force_login(self.manager)
                    self.assertRedirects(self.client.post(reverse('create_project'), {'name': name, 'description': 'Assigned cross-role project', 'project_type': project_type, 'status': 'planning'}), reverse('assign_projects'))
                    project = Project.objects.get(name=name)
                    if allocation == 'lead':
                        response = self.client.post(reverse('admin_assign_project'), {'project_id': project.pk, 'assigned_user': self.finance.pk, 'return_to': 'project_workspace'})
                    else:
                        response = self.client.post(reverse('assign_team_member', args=[project.pk]), {'team_member': member.pk, 'responsibility': 'Deliver assigned project tasks.'})
                    self.assertEqual(response.status_code, 302)
                    self.client.force_login(self.finance)
                    self.assertContains(self.client.get(reverse('my_projects')), name)
                    page = self.client.get(reverse('project_tasks', args=[project.pk]))
                    self.assertTemplateUsed(page, 'adminpanel/index.html')
                    self.assertEqual(page.context['task_form'].initial['assigned_to'], self.finance.pk)
                    payload = {'title': f'Own task {name}', 'status': 'todo', 'task_type': 'Other', 'priority': 'Medium', 'assigned_to': self.finance.pk}
                    self.assertRedirects(self.client.post(reverse('add_task', args=[project.pk]), payload), reverse('project_tasks', args=[project.pk]))
                    task = Task.objects.get(project=project, title=payload['title'])
                    self.assertEqual((task.created_by_id, task.assigned_to_id), (self.finance.pk, self.finance.pk))
                    payload.update(title=f'Own subtask {name}', parent_task=task.pk)
                    self.assertRedirects(self.client.post(reverse('add_task', args=[project.pk]), payload), reverse('project_tasks', args=[project.pk]))
                    subtask = Task.objects.get(project=project, parent_task=task)
                    self.assertContains(self.client.get(reverse('financial_kanban')), subtask.title)
                    self.client.force_login(self.manager)
                    self.assertContains(self.client.get(reverse('project_tasks', args=[project.pk])), subtask.title)
                    self.client.force_login(self.other)
                    self.assertNotContains(self.client.get(reverse('my_projects')), name)

    def test_finance_cannot_create_tasks_in_unassigned_projects_or_choose_foreign_parent(self):
        private = Project.objects.create(name='Unassigned private project', created_by=self.other, assigned_user=self.other, research_centre=self.centre)
        parent = Task.objects.create(project=private, title='Other project parent', assigned_to=self.other)
        payload = {'title': 'Rejected task', 'status': 'todo', 'task_type': 'Other', 'priority': 'Low', 'assigned_to': self.finance.pk}
        self.assertEqual(self.client.post(reverse('add_task', args=[private.pk]), payload).status_code, 404)
        response = self.client.post(reverse('add_task', args=[self.project.pk]), dict(payload, parent_task=parent.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'adminpanel/index.html')
        self.assertFalse(Task.objects.filter(title='Rejected task').exists())
        self.assertNotContains(response, 'href="' + reverse('manager_dashboard') + '"')
