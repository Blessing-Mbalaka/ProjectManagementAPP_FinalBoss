from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from manager.models import Book, Conference, Paper
from projects.models import Project, Task


User = get_user_model()


class WorkbookImportModelTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="workbook-manager",
            role="manager",
        )

    def project(self, name):
        return Project.objects.create(
            name=name,
            project_type="software",
            status="planning",
            created_by=self.manager,
        )

    def test_project_portfolio_is_nullable_and_indexed(self):
        project = self.project("Portfolio-free")

        self.assertIsNone(project.portfolio)
        self.assertTrue(Project._meta.get_field("portfolio").db_index)

    def test_task_import_key_is_unique_only_within_project(self):
        first_project = self.project("First")
        second_project = self.project("Second")
        Task.objects.create(project=first_project, title="Plan", import_key="task:plan")
        Task.objects.create(project=second_project, title="Plan", import_key="task:plan")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Task.objects.create(project=first_project, title="Duplicate", import_key="task:plan")

    def test_manual_tasks_can_keep_null_import_keys(self):
        project = self.project("Manual tasks")

        Task.objects.create(project=project, title="First manual task")
        Task.objects.create(project=project, title="Second manual task")

        self.assertEqual(project.tasks.filter(import_key__isnull=True).count(), 2)

    def test_book_supports_linked_lead_and_multiple_coauthors(self):
        lead = User.objects.create_user(username="lead-author")
        first = User.objects.create_user(username="first-author")
        second = User.objects.create_user(username="second-author")
        book = Book.objects.create(
            title="Collaborative Book",
            lead_author="",
            lead_author_user=lead,
            created_by=self.manager,
        )

        book.co_authors_users.set([first, second])

        self.assertEqual(book.lead_author_user, lead)
        self.assertCountEqual(book.co_authors_users.all(), [first, second])

    def test_publications_default_external_authors_to_empty_list(self):
        book = Book.objects.create(title="Book", lead_author="", created_by=self.manager)
        paper = Paper.objects.create(
            title="Paper",
            lead_author="",
            paper_type="journal",
            internal_external="internal",
            version="1.0",
            manuscript="",
            created_by=self.manager,
        )
        conference = Conference.objects.create(
            title="Conference paper",
            conference_name="Conference",
            lead_author="",
            internal_external="internal",
            status="draft",
            created_by=self.manager,
        )

        self.assertEqual(book.external_authors, [])
        self.assertEqual(paper.external_authors, [])
        self.assertEqual(conference.external_authors, [])
