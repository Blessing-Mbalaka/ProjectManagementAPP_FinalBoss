import csv
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from adminpanel.models import ResearchCentre
from projects.models import Assignment, Project, TeamMember


User = get_user_model()


class ProjectImportTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Import Centre")
        self.manager = User.objects.create_user(
            username="manager1", role="manager", research_centre=self.centre
        )
        self.staff = User.objects.create_user(username="staff1", role="staff", research_centre=self.centre)
        TeamMember.objects.create(user=self.staff, full_name="Staff One", role="Staff")

    def write_csv(self, rows, *, bom=False):
        handle = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="", encoding="utf-8-sig" if bom else "utf-8")
        writer = csv.DictWriter(handle, fieldnames=[
            "import_key", "project_name", "description", "project_type", "status", "due_date",
            "project_manager_username", "research_centre", "team_usernames",
        ])
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return handle.name

    def valid_row(self, **overrides):
        row = {
            "import_key": "project-001", "project_name": "Imported Project", "description": "Initial",
            "project_type": "software", "status": "planning", "due_date": "2027-03-31",
            "project_manager_username": "manager1", "research_centre": self.centre.name,
            "team_usernames": "staff1",
        }
        row.update(overrides)
        return row

    def test_dry_run_accepts_bom_and_writes_nothing(self):
        path = self.write_csv([self.valid_row()], bom=True)
        call_command("import_projects", path, dry_run=True)
        self.assertFalse(Project.objects.exists())

    def test_live_import_is_idempotent_and_assigns_manager_and_team(self):
        path = self.write_csv([self.valid_row()])
        call_command("import_projects", path)
        project = Project.objects.get(import_key="project-001")
        self.assertEqual(project.assigned_user, self.manager)
        self.assertTrue(Assignment.objects.filter(project=project, team_member__user=self.staff).exists())

        path = self.write_csv([self.valid_row(description="Updated")])
        call_command("import_projects", path)
        project.refresh_from_db()
        self.assertEqual(project.description, "Updated")
        self.assertEqual(Project.objects.count(), 1)

    def test_invalid_username_rejects_whole_batch_before_writes(self):
        path = self.write_csv([
            self.valid_row(),
            self.valid_row(import_key="project-002", project_manager_username="missing-user"),
        ])
        with self.assertRaises(CommandError):
            call_command("import_projects", path)
        self.assertFalse(Project.objects.exists())
