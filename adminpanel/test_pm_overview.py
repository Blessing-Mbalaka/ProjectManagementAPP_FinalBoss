from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from adminpanel.models import ResearchCentre
from projects.models import Assignment, Project, Task, TeamMember


User = get_user_model()


class ProjectManagementOverviewTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Overview Centre")
        self.other_centre = ResearchCentre.objects.create(name="Other Centre")
        self.admin = User.objects.create_user(
            username="overview-admin",
            password="pass",
            role="admin",
        )
        self.centre_head = User.objects.create_user(
            username="overview-head",
            password="pass",
            role="centrehead",
            research_centre=self.centre,
        )
        self.staff = User.objects.create_user(
            username="overview-staff",
            first_name="Amina",
            last_name="Ndlovu",
            password="pass",
            role="staff",
            research_centre=self.centre,
        )
        self.idle_staff = User.objects.create_user(
            username="idle-staff",
            first_name="Bongani",
            last_name="Dube",
            password="pass",
            role="staff",
            research_centre=self.centre,
        )
        self.outside_staff = User.objects.create_user(
            username="outside-staff",
            first_name="Carmen",
            last_name="Pillay",
            password="pass",
            role="staff",
            research_centre=self.other_centre,
        )
        self.project = Project.objects.create(
            name="Research Portal",
            assigned_user=self.staff,
            created_by=self.admin,
            research_centre=self.centre,
        )
        self.parent_task = Task.objects.create(
            title="Prepare release",
            project=self.project,
            assigned_to=self.staff,
            created_by=self.admin,
            status="in_progress",
        )
        self.subtask = Task.objects.create(
            title="Run acceptance tests",
            project=self.project,
            parent_task=self.parent_task,
            assigned_to=self.staff,
            created_by=self.admin,
            status="todo",
        )

    def test_admin_sees_people_projects_tasks_and_kanban_links(self):
        self.client.force_login(self.admin)

        response = self.client.get("/adminpanel/pm-overview/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project Management Overview")
        self.assertContains(response, "Amina Ndlovu")
        self.assertContains(response, self.project.name)
        self.assertContains(response, "Project type")
        self.assertContains(response, self.project.get_project_type_display())
        self.assertContains(response, "Project timeline preview")
        self.assertContains(response, "Open full Gantt")
        self.assertContains(response, reverse("admin_ganttchart"))
        self.assertEqual(response.context["gantt_preview_total"], 1)
        self.assertEqual(response.context["gantt_preview"][0]["project"], self.project)
        self.assertContains(response, self.parent_task.title)
        self.assertContains(response, self.subtask.title)
        full_kanban_url = f'{reverse("admin_kanban")}?user={self.staff.id}'
        fragment_url = reverse("admin_user_kanban", args=[self.staff.id])
        self.assertContains(response, full_kanban_url)
        self.assertNotContains(response, f'href="{fragment_url}"')
        self.assertContains(response, "Bongani Dube")
        self.assertContains(response, "No projects assigned")

    def test_centre_head_sees_only_people_in_their_centre(self):
        self.client.force_login(self.centre_head)

        response = self.client.get("/adminpanel/pm-overview/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff.get_full_name())
        self.assertNotContains(response, self.outside_staff.get_full_name())
        self.assertContains(response, "Gantt Chart")

    def test_centre_head_sidebar_hides_manage_users_and_links_editable_kanban(self):
        self.client.force_login(self.centre_head)

        response = self.client.get(reverse('overview'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '>Manage Users<')
        self.assertContains(response, 'Team Monitoring Kanban')
        self.assertContains(response, 'My Editable Kanban')
        self.assertContains(response, reverse('manager_kanban'))

    def test_admin_sidebar_keeps_manage_users(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('overview'))

        self.assertContains(response, '>Manage Users<')

    def test_centre_head_can_update_tasks_in_project_assigned_to_them(self):
        assigned_project = Project.objects.create(
            name='Centre Head Assigned Project',
            assigned_user=self.centre_head,
            created_by=self.admin,
            research_centre=self.centre,
        )
        assigned_task = Task.objects.create(
            title='Centre Head Editable Task',
            project=assigned_project,
            assigned_to=self.staff,
            created_by=self.admin,
            status='todo',
        )
        self.client.force_login(self.centre_head)

        board = self.client.get(reverse('manager_kanban'))
        update = self.client.post(
            reverse('update_task_status', args=[assigned_task.id]),
            data='{"status":"in_progress"}',
            content_type='application/json',
        )

        self.assertEqual(board.status_code, 200)
        self.assertContains(board, 'My Editable Project Kanban')
        self.assertContains(board, assigned_project.name)
        self.assertContains(board, assigned_task.title)
        self.assertTemplateUsed(board, 'manager/manager_kanban.html')
        self.assertTemplateUsed(board, 'adminpanel/index.html')
        self.assertEqual(update.status_code, 200)
        self.assertTrue(update.json()['success'])
        assigned_task.refresh_from_db()
        self.assertEqual(assigned_task.status, 'in_progress')
        self.assertEqual(assigned_task.progress, 33)

    def test_each_person_row_contains_only_their_assigned_tasks(self):
        teammate = User.objects.create_user(
            username="overview-teammate",
            first_name="Themba",
            last_name="Dlamini",
            password="pass",
            role="staff",
            research_centre=self.centre,
        )
        team_member = TeamMember.objects.create(
            user=teammate,
            full_name=teammate.get_full_name(),
            role="Author",
        )
        Assignment.objects.create(
            project=self.project,
            team_member=team_member,
            responsibility="Assigned chapter only",
        )
        teammate_task = Task.objects.create(
            title="Write assigned chapter",
            project=self.project,
            assigned_to=teammate,
            created_by=self.admin,
        )
        generic_tracker = Task.objects.create(
            title="Chapter: manager-only tracker",
            project=self.project,
            assigned_to=None,
            created_by=self.staff,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("pm_overview"))

        overview = {entry["user"].id: entry for entry in response.context["people_overview"]}
        staff_tasks = overview[self.staff.id]["projects"][0]["tasks"]
        teammate_tasks = overview[teammate.id]["projects"][0]["tasks"]
        self.assertEqual({task.id for task in staff_tasks}, {self.parent_task.id, self.subtask.id})
        self.assertEqual([task.id for task in teammate_tasks], [teammate_task.id])
        self.assertNotIn(generic_tracker.id, {task.id for task in staff_tasks})
        self.assertContains(response, "2 assigned tasks")
        self.assertContains(response, "1 assigned task")
        self.assertContains(response, "task-list-shell")
        self.assertContains(response, "pm-overview-scroll")

    def test_creator_only_project_is_shown_as_not_assigned(self):
        manager = User.objects.create_user(
            username="creator-manager",
            first_name="Created",
            last_name="Manager",
            password="pass",
            role="manager",
            research_centre=self.centre,
        )
        project = Project.objects.create(
            name="Legacy creator project",
            created_by=manager,
            research_centre=self.centre,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("pm_overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, project.name)
        self.assertContains(response, "Created, not assigned")

    def test_staff_cannot_open_project_management_overview(self):
        self.client.force_login(self.staff)

        response = self.client.get("/adminpanel/pm-overview/")

        self.assertEqual(response.status_code, 302)


class ManagerKanbanEmptyStateTests(TestCase):
    def test_manager_without_projects_sees_empty_state_instead_of_server_error(self):
        manager = User.objects.create_user(
            username="empty-manager",
            password="pass",
            role="manager",
        )
        client = Client(raise_request_exception=False)
        client.force_login(manager)

        response = client.get(reverse("manager_kanban"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No projects have been assigned to you yet")
        self.assertNotContains(response, 'data-bs-target="#addTaskModal"')


class ExecutiveOverviewInsightsTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Insights Centre")
        self.other_centre = ResearchCentre.objects.create(name="Outside Insights Centre")
        self.head = User.objects.create_user(
            username="insights-head",
            password="pass",
            role="centrehead",
            research_centre=self.centre,
        )
        self.owner = User.objects.create_user(
            username="insights-owner",
            password="pass",
            role="staff",
            research_centre=self.centre,
        )
        overdue = Project.objects.create(
            name="Overdue Book",
            project_type="book",
            status="in-progress",
            due_date=timezone.localdate() - timedelta(days=1),
            assigned_user=self.owner,
            research_centre=self.centre,
        )
        completed = Project.objects.create(
            name="Completed Paper",
            project_type="paper",
            status="completed",
            assigned_user=self.owner,
            research_centre=self.centre,
        )
        Project.objects.create(
            name="Outside Software Project",
            project_type="software",
            status="planning",
            research_centre=self.other_centre,
        )
        Task.objects.create(project=overdue, title="Finished chapter", status="done", assigned_to=self.owner)
        Task.objects.create(project=overdue, title="Open chapter", status="todo", assigned_to=self.owner)
        Task.objects.create(project=completed, title="Published", status="done", assigned_to=self.owner)

    def test_centre_head_sees_scoped_project_mix_and_delivery_health(self):
        self.client.force_login(self.head)

        response = self.client.get(reverse("overview"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_stats"]["projects"], 2)
        self.assertEqual(response.context["portfolio_health"]["average_progress"], 75)
        self.assertEqual(response.context["portfolio_health"]["overdue"], 1)
        self.assertEqual(
            {item["value"]: item["count"] for item in response.context["project_mix"]},
            {"book": 1, "paper": 1},
        )
        self.assertContains(response, "Project Mix")
        self.assertContains(response, "Delivery Health")
        self.assertNotContains(response, "Outside Software Project")
