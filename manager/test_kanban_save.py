from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from adminpanel.models import ResearchCentre
from projects.models import Project, Task


User = get_user_model()


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class ManagerKanbanSaveTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Kanban Save Centre")
        self.manager = User.objects.create_user(
            username="kanban-save-manager",
            password="pass",
            role="manager",
            research_centre=self.centre,
        )
        self.other_manager = User.objects.create_user(
            username="other-kanban-manager",
            password="pass",
            role="manager",
            research_centre=self.centre,
        )
        self.project = Project.objects.create(
            name="Editable project",
            created_by=self.manager,
            assigned_user=self.manager,
            research_centre=self.centre,
        )
        self.other_project = Project.objects.create(
            name="Another manager's project",
            created_by=self.other_manager,
            assigned_user=self.other_manager,
            research_centre=self.centre,
        )
        self.task = Task.objects.create(
            title="Original task",
            project=self.project,
            created_by=self.manager,
            status="todo",
            priority="Low",
            task_type="Other",
        )
        self.client.force_login(self.manager)

    def test_ajax_edit_persists_status_and_returns_updated_progress(self):
        response = self.client.post(
            reverse("edit_task", args=[self.task.id]),
            {
                "title": "Saved task",
                "project": self.project.id,
                "status": "done",
                "priority": "High",
                "task_type": "Testing",
                "due_date": "2030-06-15",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["task"]["progress"], 100)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Saved task")
        self.assertEqual(self.task.status, "done")
        self.assertEqual(self.task.progress, 100)
        self.assertEqual(self.task.priority, "High")
        self.assertEqual(self.task.task_type, "Testing")

    def test_edit_rejects_project_id_outside_manager_workspace(self):
        response = self.client.post(
            reverse("edit_task", args=[self.task.id]),
            {
                "title": self.task.title,
                "project": self.other_project.id,
                "status": "review",
                "priority": "Low",
                "task_type": "Other",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
        self.task.refresh_from_db()
        self.assertEqual(self.task.project, self.project)
        self.assertEqual(self.task.status, "todo")

    def test_drag_save_returns_progress_and_rejects_invalid_status(self):
        saved = self.client.post(
            reverse("update_task_status", args=[self.task.id]),
            data='{"status":"in_progress"}',
            content_type="application/json",
        )
        invalid = self.client.post(
            reverse("update_task_status", args=[self.task.id]),
            data='{"status":"not-a-column"}',
            content_type="application/json",
        )

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["progress"], 33)
        self.assertEqual(invalid.status_code, 400)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "in_progress")
        self.assertEqual(self.task.progress, 33)

    def test_board_contains_non_blocking_save_feedback(self):
        response = self.client.get(reverse("manager_kanban"))

        self.assertContains(response, "kanban-edit-form")
        self.assertContains(response, "Saving…")
        self.assertContains(response, "kanbanToastContainer")
        self.assertContains(response, "Task saved successfully.")

