from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from projects.models import Project, Task, TeamMember, Assignment
from adminpanel.models import ResearchCentre
from datetime import datetime, date

User = get_user_model()


class StaffKanbanProjectFilteringTests(TestCase):
    """Test staff_kanban view and project filtering logic"""

    def setUp(self):
        """Create test users, projects, and assignments"""
        self.centre = ResearchCentre.objects.create(name='Staff Kanban Centre')
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin_user',
            password='testpass123',
            is_staff=True
        )
        self.staff_user1 = User.objects.create_user(
            username='staff1',
            password='testpass123',
            research_centre=self.centre,
        )
        self.staff_user2 = User.objects.create_user(
            username='staff2',
            password='testpass123',
            research_centre=self.centre,
        )

        # Create TeamMember records
        self.team_member1 = TeamMember.objects.create(
            user=self.staff_user1,
            full_name='Staff One',
            role='Team Member'
        )
        self.team_member2 = TeamMember.objects.create(
            user=self.staff_user2,
            full_name='Staff Two',
            role='Team Member'
        )

        # Create projects
        # Project 1: Assigned via assigned_user field to staff_user1
        self.project_direct_assigned = Project.objects.create(
            name='Direct Assigned Project',
            description='Assigned via assigned_user field',
            project_type='software',
            status='in-progress',
            created_by=self.admin_user,
            assigned_user=self.staff_user1
        )

        # Project 2: Assigned via Assignment/TeamMember to staff_user1
        self.project_via_assignment = Project.objects.create(
            name='Assignment Project',
            description='Assigned via Assignment table',
            project_type='software',
            status='in-progress',
            created_by=self.admin_user
        )
        Assignment.objects.create(
            project=self.project_via_assignment,
            team_member=self.team_member1,
            responsibility='Lead Developer'
        )

        # Project 3: Assigned to staff_user2 only
        self.project_staff2 = Project.objects.create(
            name='Staff2 Only Project',
            description='Assigned only to staff2',
            project_type='software',
            status='planning',
            created_by=self.admin_user,
            assigned_user=self.staff_user2
        )

        # Project 4: Not assigned to anyone
        self.project_unassigned = Project.objects.create(
            name='Unassigned Project',
            description='Not assigned to any staff',
            project_type='software',
            status='planning',
            created_by=self.admin_user
        )

        self.client = Client()

    def test_staff_kanban_shows_direct_assigned_projects(self):
        """Staff should see projects assigned via assigned_user field"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('staff_kanban'))
        
        self.assertEqual(response.status_code, 200)
        projects = response.context['projects']
        project_ids = [p.id for p in projects]
        
        self.assertIn(
            self.project_direct_assigned.id,
            project_ids,
            "Direct assigned project should be visible"
        )

    def test_staff_kanban_shows_assignment_projects(self):
        """Staff should see projects assigned via Assignment/TeamMember"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('staff_kanban'))
        
        self.assertEqual(response.status_code, 200)
        projects = response.context['projects']
        project_ids = [p.id for p in projects]
        
        self.assertIn(
            self.project_via_assignment.id,
            project_ids,
            "Assignment project should be visible"
        )

    def test_staff_kanban_shows_both_assignment_methods(self):
        """Staff should see projects from both assignment methods"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('staff_kanban'))
        
        self.assertEqual(response.status_code, 200)
        projects = response.context['projects']
        project_ids = [p.id for p in projects]
        
        # Staff1 should see both their projects
        self.assertIn(self.project_direct_assigned.id, project_ids)
        self.assertIn(self.project_via_assignment.id, project_ids)

    def test_staff_kanban_hides_other_staff_projects(self):
        """Staff should NOT see projects assigned to other staff members"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('staff_kanban'))
        
        projects = response.context['projects']
        project_ids = [p.id for p in projects]
        
        self.assertNotIn(
            self.project_staff2.id,
            project_ids,
            "Staff2's project should not be visible to Staff1"
        )

    def test_staff_kanban_hides_unassigned_projects(self):
        """Staff should NOT see projects with no assignments"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('staff_kanban'))
        
        projects = response.context['projects']
        project_ids = [p.id for p in projects]
        
        self.assertNotIn(
            self.project_unassigned.id,
            project_ids,
            "Unassigned project should not be visible"
        )

    def test_staff_kanban_modal_project_count(self):
        """Modal should show exactly the assigned projects"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('staff_kanban'))
        
        projects = response.context['projects']
        # Staff1 should see exactly 2 projects
        self.assertEqual(
            projects.count(),
            2,
            "Staff1 should see exactly 2 projects (1 direct + 1 via assignment)"
        )


class StaffCreateTaskTests(TestCase):
    """Test staff_create_task view and security"""

    def setUp(self):
        """Create test users and projects"""
        self.admin_user = User.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True
        )
        self.staff_user = User.objects.create_user(
            username='staff1',
            password='testpass123'
        )
        self.other_staff = User.objects.create_user(
            username='staff2',
            password='testpass123'
        )

        self.team_member = TeamMember.objects.create(
            user=self.staff_user,
            full_name='Staff One',
            role='Team Member'
        )

        # Project assigned to staff_user
        self.assigned_project = Project.objects.create(
            name='Assigned Project',
            project_type='software',
            status='in-progress',
            created_by=self.admin_user,
            assigned_user=self.staff_user
        )

        # Project not assigned to staff_user
        self.other_project = Project.objects.create(
            name='Other Project',
            project_type='software',
            status='planning',
            created_by=self.admin_user,
            assigned_user=self.other_staff
        )

        self.client = Client()

    def test_staff_create_task_endpoint_is_forbidden(self):
        """Staff can only update existing Kanban task status and comments."""
        self.client.login(username='staff1', password='testpass123')

        response = self.client.post(reverse('staff_create_task'), {
            'title': 'New Task',
            'status': 'todo',
            'project_id': self.assigned_project.id,
        })

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.filter(title='New Task').exists())


class StaffKanbanTaskGroupingTests(TestCase):
    """Test task grouping by status in staff_kanban"""

    def setUp(self):
        """Create test data"""
        self.staff_user = User.objects.create_user(
            username='staff1',
            password='testpass123'
        )

        self.project = Project.objects.create(
            name='Test Project',
            project_type='software',
            status='in-progress',
            created_by=User.objects.create_user(
                username='admin',
                password='testpass123'
            ),
            assigned_user=self.staff_user
        )

        # Create tasks with different statuses
        Task.objects.create(
            title='Todo Task',
            status='todo',
            assigned_to=self.staff_user,
            created_by=self.staff_user,
            project=self.project
        )
        Task.objects.create(
            title='In Progress Task',
            status='in_progress',
            assigned_to=self.staff_user,
            created_by=self.staff_user,
            project=self.project
        )
        Task.objects.create(
            title='Review Task',
            status='review',
            assigned_to=self.staff_user,
            created_by=self.staff_user,
            project=self.project
        )
        Task.objects.create(
            title='Done Task',
            status='done',
            assigned_to=self.staff_user,
            created_by=self.staff_user,
            project=self.project
        )

        self.client = Client()

    def test_tasks_grouped_by_status(self):
        """Tasks should be properly grouped by status"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('staff_kanban'))

        grouped_tasks = response.context['grouped_tasks']
        
        self.assertEqual(grouped_tasks['todo'].count(), 1)
        self.assertEqual(grouped_tasks['in_progress'].count(), 1)
        self.assertEqual(grouped_tasks['review'].count(), 1)
        self.assertEqual(grouped_tasks['done'].count(), 1)

    def test_project_assignee_sees_the_full_assigned_project_task_pool(self):
        """Project assignees work from the project's complete task pool."""
        other_staff = User.objects.create_user(
            username='staff2',
            password='testpass123'
        )
        Task.objects.create(
            title='Other Staff Task',
            status='todo',
            assigned_to=other_staff,
            created_by=other_staff,
            project=self.project
        )

        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('staff_kanban'))

        grouped_tasks = response.context['grouped_tasks']
        all_tasks = (
            grouped_tasks['todo'] |
            grouped_tasks['in_progress'] |
            grouped_tasks['review'] |
            grouped_tasks['done']
        )
        
        self.assertEqual(all_tasks.count(), 5)
