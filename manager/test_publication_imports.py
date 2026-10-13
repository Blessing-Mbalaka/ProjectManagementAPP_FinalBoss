import csv
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from adminpanel.models import ResearchCentre
from manager.models import Book, Conference, Paper
from projects.models import Project


User = get_user_model()


class PublicationImportTests(TestCase):
    FIELDS = [
        "kind", "import_key", "title", "description", "status", "due_date", "internal_external",
        "paper_type", "version", "abstract", "conference_name", "conference_date", "location",
        "publisher", "total_chapters", "completed_chapters", "lead_author", "lead_author_username",
        "co_author_usernames", "reviewer_usernames", "project_manager_username", "research_centre",
        "team_usernames", "target_journal", "submission_date", "decision_date",
    ]

    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Output Centre")
        self.manager = User.objects.create_user(username="manager1", role="manager", research_centre=self.centre)
        self.author = User.objects.create_user(username="author1", role="staff", research_centre=self.centre)
        self.reviewer = User.objects.create_user(username="reviewer1", role="staff", research_centre=self.centre)

    def write_csv(self, rows):
        handle = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="", encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=self.FIELDS)
        writer.writeheader()
        writer.writerows(rows)
        handle.close()
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return handle.name

    def base(self, kind, key, title, status):
        return {
            "kind": kind, "import_key": key, "title": title, "description": "Description", "status": status,
            "due_date": "2027-06-30", "internal_external": "external", "paper_type": "journal",
            "version": "1.0", "abstract": "Abstract", "conference_name": "Annual Conference",
            "conference_date": "2027-05-30", "location": "Johannesburg", "publisher": "Publisher",
            "total_chapters": "5", "completed_chapters": "1", "lead_author": "Author One",
            "lead_author_username": "author1", "co_author_usernames": "", "reviewer_usernames": "reviewer1",
            "project_manager_username": "manager1", "research_centre": self.centre.name,
            "team_usernames": "author1", "target_journal": "Journal", "submission_date": "2027-01-01",
            "decision_date": "",
        }

    def test_imports_each_publication_kind_with_linked_projects_and_user_relations(self):
        path = self.write_csv([
            self.base("book", "book-1", "Book One", "writing"),
            self.base("paper", "paper-1", "Paper One", "submitted"),
            self.base("conference", "conference-1", "Conference One", "submitted"),
        ])
        call_command("import_publications", path)

        self.assertEqual((Book.objects.count(), Paper.objects.count(), Conference.objects.count()), (1, 1, 1))
        self.assertEqual(Project.objects.count(), 3)
        self.assertEqual(Paper.objects.get().lead_author_user, self.author)
        self.assertEqual(list(Paper.objects.get().assigned_reviewers.all()), [self.reviewer])
        self.assertEqual(Conference.objects.get().project.assigned_user, self.manager)

    def test_invalid_row_prevents_orphaned_publications_and_projects(self):
        bad = self.base("paper", "paper-bad", "Bad", "not-a-status")
        path = self.write_csv([self.base("book", "book-good", "Good", "writing"), bad])
        with self.assertRaises(CommandError):
            call_command("import_publications", path)
        self.assertFalse(Project.objects.exists())
        self.assertFalse(Book.objects.exists())
        self.assertFalse(Paper.objects.exists())

    def test_rerun_updates_existing_publication_without_duplicate_project(self):
        row = self.base("book", "book-1", "Book One", "writing")
        path = self.write_csv([row])
        call_command("import_publications", path)
        row["description"] = "Updated description"
        path = self.write_csv([row])
        call_command("import_publications", path)

        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(Project.objects.count(), 1)
        self.assertEqual(Book.objects.get().description, "Updated description")

    def test_cross_centre_contributor_is_rejected_before_writes(self):
        other_centre = ResearchCentre.objects.create(name="Other Centre")
        User.objects.create_user(username="external-user", role="staff", research_centre=other_centre)
        row = self.base("paper", "paper-cross-centre", "Cross Centre", "draft")
        row["co_author_usernames"] = "external-user"
        path = self.write_csv([row])

        with self.assertRaises(CommandError):
            call_command("import_publications", path)

        self.assertFalse(Project.objects.exists())
