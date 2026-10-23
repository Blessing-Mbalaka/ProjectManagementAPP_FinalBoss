from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from adminpanel.models import ResearchCentre
from projects.models import Project, Task


User = get_user_model()


class AdminKanbanWorkflowTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Admin Workflow Centre")
        self.admin = User.objects.create_user(username="admin-worker", password="pass", role="admin")
        self.other_admin = User.objects.create_user(username="other-admin", password="pass", role="admin")
        self.staff = User.objects.create_user(
            username="staff-worker", password="pass", role="staff", research_centre=self.centre
        )
        self.project = Project.objects.create(
            name="Critical Delivery",
            description="Complete project description",
            project_type="software",
            status="in-progress",
            due_date=timezone.localdate() + timedelta(days=5),
            created_by=self.other_admin,
            assigned_user=self.admin,
            research_centre=self.centre,
        )
        self.task = Task.objects.create(
            project=self.project,
            title="Prepare delivery",
            task_type="Testing",
            priority="High",
            status="todo",
            due_date=timezone.localdate() - timedelta(days=1),
            assigned_to=self.admin,
            created_by=self.other_admin,
            comments="Initial comment",
        )
        self.other_project = Project.objects.create(name="Other", created_by=self.other_admin)
        self.other_task = Task.objects.create(
            project=self.other_project, title="Private task", created_by=self.other_admin
        )
        self.client.force_login(self.admin)

    def test_personal_board_does_not_expand_admin_project_permissions(self):
        unassigned_tracker = Task.objects.create(
            project=self.project,
            title="Manager-only project tracker",
            created_by=self.admin,
        )

        response = self.client.get(reverse("admin_user_kanban", args=[self.admin.id]))

        self.assertContains(response, self.task.title)
        self.assertNotContains(response, unassigned_tracker.title)

    def test_admin_my_projects_shows_assigned_project_and_not_unrelated_project(self):
        response = self.client.get(reverse("admin_my_projects"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, self.other_project.name)

    def test_admin_can_update_status_and_comments_but_not_task_identity(self):
        response = self.client.post(
            reverse("admin_my_task_update", args=[self.task.id]),
            {"status": "review", "comments": "Ready for review", "title": "Changed"},
        )

        self.assertRedirects(response, reverse("admin_my_projects"))
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "review")
        self.assertEqual(self.task.comments, "Ready for review")
        self.assertEqual(self.task.title, "Prepare delivery")

    def test_admin_cannot_update_an_unassigned_task(self):
        response = self.client.post(
            reverse("admin_my_task_update", args=[self.other_task.id]),
            {"status": "done", "comments": "Not allowed"},
        )

        self.assertEqual(response.status_code, 404)
        self.other_task.refresh_from_db()
        self.assertEqual(self.other_task.status, "todo")

    def test_staff_filter_includes_admin_users_and_detail_modal_has_project_table(self):
        board = self.client.get(reverse("admin_kanban"))
        detail = self.client.get(reverse("admin_user_kanban", args=[self.admin.id]))

        self.assertContains(board, self.admin.username)
        self.assertContains(detail, 'data-last-updated=')
        self.assertContains(detail, "Project details")
        self.assertContains(detail, "Research centre")
        self.assertContains(detail, "Project manager")
        self.assertContains(detail, "Task due date")
        self.assertContains(detail, "Overdue")
        self.assertContains(detail, self.project.description)

    def test_readonly_board_preselects_requested_inspectable_user(self):
        response = self.client.get(reverse("admin_kanban"), {"user": self.staff.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_user_id"], self.staff.id)
        self.assertContains(
            response,
            f'<option value="{self.staff.id}" selected>',
        )

    def test_refreshed_staff_board_contains_another_clients_committed_update(self):
        updater = Client()
        updater.force_login(self.admin)
        updater.post(
            reverse("admin_my_task_update", args=[self.task.id]),
            {"status": "in_progress", "comments": "Update from another client"},
        )

        refreshed = self.client.get(reverse("admin_user_kanban", args=[self.admin.id]))

        self.assertContains(refreshed, "Update from another client")
        self.assertContains(refreshed, "In Progress")
