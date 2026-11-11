from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from projects.models import Project, Task, Assignment, TeamMember
from projects.work_scope import workable_tasks_for

@override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},"staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class StaffProjectTaskTests(TestCase):
    def setUp(self):
        from adminpanel.models import ResearchCentre
        self.centre=ResearchCentre.objects.create(name="Task creation centre")
        U=get_user_model()
        self.manager=U.objects.create_user('manager',role='manager',research_centre=self.centre)
        self.staff=U.objects.create_user('staff',role='staff',research_centre=self.centre)
        self.peer=U.objects.create_user('peer',role='staff',research_centre=self.centre)
        self.outsider=U.objects.create_user('outsider',role='staff',research_centre=self.centre)
        self.project=Project.objects.create(name='Delegated delivery',created_by=self.manager,research_centre=self.centre)
        for user in [self.staff,self.peer]:
            member=TeamMember.objects.create(user=user,full_name=user.username,role='Team Member')
            Assignment.objects.create(project=self.project,team_member=member,responsibility='Deliver')
        self.client.force_login(self.staff)
        self.payload={'title':'Delegated follow-up','assigned_to':self.peer.pk,'status':'todo','priority':'High','task_type':'Testing'}

    def test_staff_creates_using_manager_endpoint_and_stakeholders_see_task(self):
        response=self.client.post(reverse('add_task',args=[self.project.pk]),self.payload)
        self.assertRedirects(response,reverse('project_tasks',args=[self.project.pk]))
        task=Task.objects.get(title=self.payload['title'])
        self.assertEqual(task.created_by,self.staff)
        self.assertEqual(task.project,self.project)
        self.assertEqual(task.assigned_to,self.peer)
        for user in [self.staff,self.peer,self.manager]:
            self.client.force_login(user)
            self.assertContains(self.client.get(reverse('project_tasks',args=[self.project.pk])),task.title)
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse('manager_kanban')),task.title)
        self.assertContains(self.client.get(reverse('assign_projects'), {'project_id':self.project.pk}),task.title)
        self.assertIn(task,workable_tasks_for(self.manager))
        self.assertIn(task,workable_tasks_for(self.peer))
        self.assertNotIn(task,workable_tasks_for(self.staff))

    def test_unassigned_staff_cannot_read_or_create(self):
        self.client.force_login(self.outsider)
        for name in ['project_tasks','add_task']:
            response=self.client.get(reverse(name,args=[self.project.pk]))
            self.assertEqual(response.status_code,404)
        self.assertEqual(self.client.post(reverse('add_task',args=[self.project.pk]),self.payload).status_code,404)
        self.assertFalse(Task.objects.exists())

    def test_outside_assignee_and_parent_are_rejected_without_saving(self):
        response=self.client.post(reverse('add_task',args=[self.project.pk]),dict(self.payload,assigned_to=self.outsider.pk))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Select a valid choice')
        self.assertFalse(Task.objects.exists())
        other=Project.objects.create(name='Other',created_by=self.manager)
        parent=Task.objects.create(title='Other parent',project=other,created_by=self.manager)
        response=self.client.post(reverse('add_task',args=[self.project.pk]),dict(self.payload,parent_task=parent.pk))
        self.assertContains(response,'Select a valid choice')
        self.assertEqual(Task.objects.count(),1)

    def test_direct_project_assignee_can_add_own_task(self):
        direct=Project.objects.create(name='Direct assignment',created_by=self.manager,assigned_user=self.staff)
        response=self.client.post(reverse('add_task',args=[direct.pk]),dict(self.payload,assigned_to=self.staff.pk))
        self.assertRedirects(response,reverse('project_tasks',args=[direct.pk]))
        self.assertTrue(Task.objects.filter(project=direct,assigned_to=self.staff).exists())

    def test_invalid_form_keeps_values_and_does_not_show_manager_allocation(self):
        response=self.client.post(reverse('add_task',args=[self.project.pk]),dict(self.payload,title=''))
        self.assertContains(response,'This field is required')
        self.assertNotContains(response,'Assign Project Lead')
        self.assertFalse(Task.objects.exists())
