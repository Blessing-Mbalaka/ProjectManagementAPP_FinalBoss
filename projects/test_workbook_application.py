from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from adminpanel.models import ResearchCentre
from manager.models import Book, Conference, Paper
from manager.publication_projects import sync_publication_project
from projects.models import Assignment, Project, Task
from projects.workbook_import.application import WorkbookImportError, apply_workbook_preview
from projects.workbook_import.schema import WorkbookReadResult
from projects.workbook_import.validation import validate_workbook


User = get_user_model()


class WorkbookApplicationTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Import Centre")
        self.manager = User.objects.create_user(username="manager1", role="manager", research_centre=self.centre)
        self.alice = User.objects.create_user(username="alice", role="staff", research_centre=self.centre)
        self.bob = User.objects.create_user(username="bob", role="staff", research_centre=self.centre)

    def project_row(self, kind, key, name, row):
        data = {
            "_row": row,
            "import_key": key,
            "project_name": name,
            "portfolio": "Portfolio A",
            "description": f"{name} description",
            "project_type": kind,
            "project_status": "in-progress",
            "due_date": "2027-06-30",
            "project_manager_username": "manager1",
            "research_centre": self.centre.name,
            "team_usernames": "alice",
            "publication_status": "",
            "lead_author_username": "",
            "co_author_usernames": "",
            "external_authors": "",
            "reviewer_usernames": "",
            "publisher": "",
            "total_chapters": "",
            "completed_chapters": "",
            "internal_external": "",
            "paper_type": "",
            "version": "",
            "abstract": "",
            "target_journal": "",
            "conference_name": "",
            "conference_date": "",
            "location": "",
            "submission_date": "",
            "decision_date": "",
        }
        if kind == "book":
            data.update(publication_status="writing", lead_author_username="alice", co_author_usernames="bob", external_authors="External One", publisher="Press", total_chapters="4", completed_chapters="1")
        elif kind == "paper":
            data.update(publication_status="draft", lead_author_username="alice", co_author_usernames="bob", reviewer_usernames="bob", internal_external="internal", paper_type="journal", version="1.0", abstract="Abstract")
        elif kind == "conference":
            data.update(publication_status="draft", lead_author_username="alice", internal_external="internal", conference_name="Annual Conference", conference_date="2027-05-01")
        return data

    def valid_preview(self):
        projects = [
            self.project_row("software", "software-1", "Software One", 2),
            self.project_row("book", "book-1", "Book One", 3),
            self.project_row("paper", "paper-1", "Paper One", 4),
            self.project_row("conference", "conference-1", "Conference One", 5),
        ]
        tasks = [
            {"_row": 2, "project_name": "Software One", "task_name": "Child", "parent_task": "Parent", "assigned_to": "bob", "responsibility": "Developer", "status": "todo", "priority": "Medium", "task_type": "Frontend", "due_date": "2027-04-01", "comments": "Child work"},
            {"_row": 3, "project_name": "Software One", "task_name": "Parent", "parent_task": "", "assigned_to": "alice", "responsibility": "Lead", "status": "in_progress", "priority": "High", "task_type": "Architecture", "due_date": "2027-03-01", "comments": "Parent work"},
        ]
        preview = validate_workbook(WorkbookReadResult(tuple(projects), tuple(tasks)), actor=self.manager)
        self.assertTrue(preview.is_valid, preview.errors)
        return preview

    def test_apply_creates_all_types_authors_memberships_and_task_tree_idempotently(self):
        preview = self.valid_preview()

        first = apply_workbook_preview(preview, actor=self.manager)
        second = apply_workbook_preview(preview, actor=self.manager)

        self.assertEqual(Project.objects.count(), 4)
        self.assertEqual((Book.objects.count(), Paper.objects.count(), Conference.objects.count()), (1, 1, 1))
        book = Book.objects.get()
        self.assertEqual(book.lead_author_user, self.alice)
        self.assertCountEqual(book.co_authors_users.all(), [self.bob])
        self.assertEqual(book.external_authors, ["External One"])
        software = Project.objects.get(import_key="software-1")
        self.assertEqual(software.portfolio, "Portfolio A")
        self.assertEqual(software.status, "in-progress")
        child = software.tasks.get(title="Child")
        self.assertEqual(child.parent_task.title, "Parent")
        self.assertEqual(child.assigned_to, self.bob)
        self.assertTrue(Assignment.objects.filter(project=software, team_member__user=self.bob).exists())
        self.assertEqual(Task.objects.count(), 2)
        self.assertEqual(first.created_projects, 4)
        self.assertEqual(second.updated_projects, 4)

    def test_application_failure_rolls_back_every_related_write(self):
        preview = self.valid_preview()

        with patch("projects.workbook_import.application._save_tasks", side_effect=RuntimeError("database failure")):
            with self.assertRaises(RuntimeError):
                apply_workbook_preview(preview, actor=self.manager)

        self.assertFalse(Project.objects.exists())
        self.assertFalse(Book.objects.exists())
        self.assertFalse(Paper.objects.exists())
        self.assertFalse(Conference.objects.exists())
        self.assertFalse(Assignment.objects.exists())

    def test_invalid_preview_is_never_applied(self):
        preview = validate_workbook(
            WorkbookReadResult(project_rows=(self.project_row("software", "bad", "Bad", 2) | {"project_manager_username": "missing"},)),
            actor=self.manager,
        )

        with self.assertRaises(WorkbookImportError):
            apply_workbook_preview(preview, actor=self.manager)

        self.assertFalse(Project.objects.exists())

    def test_publication_sync_accepts_explicit_project_values_without_changing_legacy_calls(self):
        book = Book.objects.create(title="Synced Book", lead_author="", status="writing", created_by=self.manager)

        project = sync_publication_project(
            book,
            actor=self.manager,
            manager=self.manager,
            research_centre=self.centre,
            project_values={
                "status": "on-hold",
                "description": "Workbook description",
                "portfolio": "Research Portfolio",
            },
        )
        legacy_book = Book.objects.create(title="Legacy Book", lead_author="", status="published", created_by=self.manager)
        legacy_project = sync_publication_project(legacy_book, actor=self.manager)

        self.assertEqual(project.status, "on-hold")
        self.assertEqual(project.description, "Workbook description")
        self.assertEqual(project.portfolio, "Research Portfolio")
        self.assertEqual(legacy_project.status, "completed")
