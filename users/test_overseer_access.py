import json
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from adminpanel.models import ResearchCentre
from projects.models import Project, Task

@override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},"staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RoleWorkflowTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Workflow Centre")
        self.other = ResearchCentre.objects.create(name="Other Centre")
        self.users = {role:get_user_model().objects.create_user(role, password="test-pass", role=role, research_centre=self.centre) for role in ['admin','centrehead','overseer','financialadmin','manager','staff','dean','student','supervisor']}
        self.project = Project.objects.create(name="Assignment workflow", project_type="financial", research_centre=self.centre, created_by=self.users['manager'], assigned_user=self.users['manager'])
        self.task = Task.objects.create(title="Assigned task", project=self.project, created_by=self.users['manager'], assigned_to=self.users['staff'], status="todo")

    def test_financial_board_edit_and_drag_persist_for_admin_and_centrehead(self):
        for role in ['admin','centrehead']:
            with self.subTest(role=role):
                self.client.force_login(self.users[role])
                self.assertEqual(self.client.get(reverse('financial_kanban')).status_code,200)
                response=self.client.post(reverse('edit_task',args=[self.task.pk]), {'title':role+' saved','project':self.project.pk,'status':'review','priority':'High','task_type':'Testing'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertEqual(response.status_code,200, response.content)
                self.task.refresh_from_db()
                self.assertEqual(self.task.title,role+' saved')
                self.assertEqual(self.task.status,'review')
                response=self.client.post(reverse('update_task_status',args=[self.task.pk]),json.dumps({'status':'done'}),content_type='application/json')
                self.assertEqual(response.status_code,200)
                self.task.refresh_from_db()
                self.assertEqual(self.task.status,'done')
                self.assertEqual(self.task.progress,100)
                self.assertContains(self.client.get(reverse('financial_kanban')),role+' saved')

    def test_overseer_nonfinancial_pages_and_hidden_links(self):
        self.client.force_login(self.users['overseer'])
        for name in ['overview','assign_projects','manager_kanban','pm_overview','admin_ganttchart']:
            response=self.client.get(reverse(name))
            self.assertEqual(response.status_code,200,(name,response.status_code))
        response=self.client.get(reverse('overview'))
        for name in ['finance','financial_projects','applied_bids','financial_kanban']:
            self.assertNotContains(response,'href="'+reverse(name)+'"')
        self.assertNotContains(response,'Cost Centres')

    def test_overseer_financial_get_and_post_denied(self):
        self.client.force_login(self.users['overseer'])
        for name in ['finance','finance_readonly','financial_projects','applied_bids','financial_kanban','download_finance_summary_excel','add_cost_centre','add_expenditure','crm_reporting_data']:
            for method in [self.client.get,self.client.post]:
                self.assertEqual(method(reverse(name)).status_code,403,name)
        for tab in ['financials','reports','alerts']:
            self.assertEqual(self.client.get(reverse('crm_tab',args=[tab])).status_code,403)
        for tab in ['clients','centres','engagements','directory']:
            response=self.client.get(reverse('crm_tab',args=[tab]))
            self.assertEqual(response.status_code,200)
            self.assertNotContains(response,'<th>Revenue</th>')
            self.assertNotContains(response,'<span>Revenue</span>')

    def test_overseer_cannot_touch_other_centre_tasks(self):
        self.client.force_login(self.users['overseer'])
        project=Project.objects.create(name='Outside scope', research_centre=self.other, created_by=self.users['admin'])
        task=Task.objects.create(title='Private task',project=project,created_by=self.users['admin'])
        self.assertEqual(self.client.post(reverse('update_task_status',args=[task.pk]),json.dumps({'status':'done'}),content_type='application/json').status_code,404)

    def test_finance_navigation_has_no_publication_links(self):
        self.client.force_login(self.users['financialadmin'])
        response=self.client.get(reverse('financial_kanban'))
        self.assertEqual(response.status_code,200)
        for name in ['manager_journal','manager_book']:
            self.assertNotContains(response,'href="'+reverse(name)+'"')

    def test_overseer_updates_nonfinancial_work_and_cannot_view_financial_work(self):
        self.client.force_login(self.users['overseer'])
        project=Project.objects.create(name='Nonfinancial oversight', research_centre=self.centre, created_by=self.users['manager'])
        task=Task.objects.create(title='Oversight task', project=project, created_by=self.users['manager'])
        response=self.client.post(reverse('update_task_status',args=[task.pk]),json.dumps({'status':'done'}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        task.refresh_from_db()
        self.assertEqual(task.status,'done')
        self.assertEqual(self.client.post(reverse('update_task_status',args=[self.task.pk]),json.dumps({'status':'done'}),content_type='application/json').status_code,404)
        response=self.client.get(reverse('overview'))
        self.assertNotContains(response,'Financial / Client Bid')
        self.assertNotContains(self.client.get(reverse('assign_projects')),'value="financial"')
