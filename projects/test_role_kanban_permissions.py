from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from adminpanel.models import ResearchCentre
from projects.models import Assignment, Project, Task, TeamMember


User = get_user_model()


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class RoleKanbanBehaviorTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Kanban Centre")
        self.admin = User.objects.create_user(
            username="admin-kanban",
            password="pass",
            role="admin",
        )
        self.staff = User.objects.create_user(
            username="staff-kanban",
            password="pass",
            role="staff",
            research_centre=self.centre,
        )
        self.manager = User.objects.create_user(
            username="manager-kanban",
            password="pass",
            role="manager",
            research_centre=self.centre,
        )
        self.other_staff = User.objects.create_user(
            username="other-staff-kanban",
            password="pass",
            role="staff",
            research_centre=self.centre,
        )

        self.staff_member = TeamMember.objects.get_or_create(
            user=self.staff,
            defaults={"full_name": "Staff Kanban", "role": "Staff"},
        )[0]
        self.manager_member = TeamMember.objects.get_or_create(
            user=self.manager,
            defaults={"full_name": "Manager Kanban", "role": "Project Manager"},
        )[0]

        self.project = Project.objects.create(
            name="Assigned Research Project",
            description="Sensitive project description",
            project_type="paper",
            status="in-progress",
            due_date=timezone.localdate() - timedelta(days=1),
            research_centre=self.centre,
            created_by=self.admin,
        )
        Assignment.objects.create(
            project=self.project,
            team_member=self.staff_member,
            responsibility="Research support",
        )
        self.task = Task.objects.create(
            project=self.project,
            assigned_to=self.staff,
            created_by=self.admin,
            title="Prepare findings",
            task_type="Paper",
            priority="High",
            due_date=timezone.localdate() - timedelta(days=1),
            status="todo",
        )

    def test_staff_update_changes_only_status_and_comments(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            f"/projects/staff/edit-task/{self.task.id}/",
            {
                "status": "review",
                "comments": "Draft is ready for review.",
                "title": "Changed title",
                "task_type": "Backend",
                "priority": "Low",
                "due_date": "2035-01-01",
                "project_name": "Changed project",
            },
        )

        self.task.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("staff_kanban"),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.task.status, "review")
        self.assertEqual(getattr(self.task, "comments", ""), "Draft is ready for review.")
        self.assertEqual(self.task.title, "Prepare findings")
        self.assertEqual(self.task.task_type, "Paper")
        self.assertEqual(self.task.priority, "High")
        self.assertNotEqual(str(self.task.due_date), "2035-01-01")
        self.assertEqual(self.task.project, self.project)

    def test_staff_kanban_offers_only_status_and_comments_controls(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("staff_kanban"))

        self.assertContains(response, f'/projects/staff/edit-task/{self.task.id}/')
        self.assertContains(response, 'name="comments"')
        self.assertNotContains(response, 'data-bs-target="#addTaskModal"')
        self.assertNotContains(response, 'name="title"')
        self.assertNotContains(response, 'name="task_type"')
        self.assertNotContains(response, reverse("delete_task", args=[self.task.id]))

    def test_staff_cannot_create_or_delete_kanban_tasks(self):
        self.client.force_login(self.staff)

        create_response = self.client.post(
            reverse("staff_create_task"),
            {"title": "Unapproved task", "status": "todo"},
        )
        delete_response = self.client.post(reverse("delete_task", args=[self.task.id]))

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertFalse(Task.objects.filter(title="Unapproved task").exists())
        self.assertTrue(Task.objects.filter(id=self.task.id).exists())

    def test_manager_kanban_includes_team_assignment_projects_and_tasks(self):
        Project.objects.create(
            name="Manager direct project",
            research_centre=self.centre,
            created_by=self.admin,
            assigned_user=self.manager,
        )
        assigner_client = Client()
        manager_client = Client()
        assigner_client.force_login(self.admin)
        manager_client.force_login(self.manager)

        assignment_response = assigner_client.post(
            reverse("assign_team_member", args=[self.project.id]),
            {
                "team_member": self.manager_member.id,
                "responsibility": "Project manager",
            },
        )
        self.assertEqual(assignment_response.status_code, 302)
        self.assertTrue(
            Assignment.objects.filter(
                project=self.project,
                team_member=self.manager_member,
            ).exists()
        )

        response = manager_client.get(reverse("manager_kanban"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.project, list(response.context["projects"]))
        visible_tasks = [
            task
            for tasks in response.context["grouped_tasks"].values()
            for task in tasks
        ]
        self.assertIn(self.task, visible_tasks)

    def test_assignment_summary_does_not_expose_project_description(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("assignments"))

        self.assertContains(response, self.project.name)
        self.assertNotContains(response, self.project.description)

    def test_admin_readonly_board_has_more_details_and_overdue_state(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin_user_kanban", args=[self.staff.id]))

        self.assertContains(response, self.task.title)
        self.assertContains(response, "More")
        self.assertContains(response, self.project.description)
        self.assertContains(response, "Overdue")

    def test_manager_dashboard_omits_recent_uploads(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("manager_dashboard"))

        self.assertNotContains(response, "Recent Uploads")
        self.assertNotContains(response, 'id="uploadModal"')
        self.assertNotContains(response, 'id="uploads-list"')
