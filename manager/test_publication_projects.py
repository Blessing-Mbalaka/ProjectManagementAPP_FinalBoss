import importlib

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from adminpanel.models import ResearchCentre
from manager.models import Book, Conference, Paper
from manager.publication_projects import sync_publication_project
from projects.models import Project


User = get_user_model()


class PublicationProjectTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Publication Centre")
        self.actor = User.objects.create_user(
            username="author", password="pass", role="manager", research_centre=self.centre
        )
        self.manager = User.objects.create_user(
            username="project-manager", role="manager", research_centre=self.centre
        )

    def test_book_sync_creates_and_then_updates_one_linked_project(self):
        book = Book.objects.create(
            title="Reliable Systems",
            description="A practical book",
            status="writing",
            lead_author="Author",
            created_by=self.actor,
        )

        project = sync_publication_project(
            book, actor=self.actor, manager=self.manager, research_centre=self.centre
        )
        book.refresh_from_db()
        self.assertEqual(book.project, project)
        self.assertEqual(project.project_type, "book")
        self.assertEqual(project.assigned_user, self.manager)
        self.assertEqual(project.status, "in-progress")

        book.status = "published"
        book.save(update_fields=["status"])
        same_project = sync_publication_project(book, actor=self.actor)
        self.assertEqual(same_project.id, project.id)
        self.assertEqual(same_project.status, "completed")
        self.assertEqual(Project.objects.count(), 1)

    def test_paper_and_conference_use_project_types_and_terminal_status_maps(self):
        paper = Paper.objects.create(
            title="Research result",
            paper_type="journal",
            internal_external="external",
            lead_author="Author",
            status="published",
            version="1.0",
            manuscript="papers/result.pdf",
            created_by=self.actor,
        )
        conference = Conference.objects.create(
            title="Conference result",
            conference_name="Annual Conference",
            internal_external="external",
            lead_author="Author",
            status="presented",
            created_by=self.actor,
        )

        paper_project = sync_publication_project(paper, actor=self.actor)
        conference_project = sync_publication_project(conference, actor=self.actor)

        self.assertEqual((paper_project.project_type, paper_project.status), ("paper", "completed"))
        self.assertEqual((conference_project.project_type, conference_project.status), ("conference", "completed"))

    def test_publication_without_creator_can_link_to_project_and_page_handles_missing_link(self):
        unlinked = Book.objects.create(title="Legacy Book", lead_author="Unknown", created_by=self.actor)
        linked = Book.objects.create(title="Imported Book", lead_author="Unknown", created_by=None)

        project = sync_publication_project(linked, actor=None)
        self.assertIsNone(project.created_by)

        self.client.force_login(self.actor)
        response = self.client.get(reverse("manager_book"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project setup pending")

    def test_backfill_links_null_creator_and_duplicate_title_records_deterministically(self):
        first = Book.objects.create(title="Duplicate Legacy Title", lead_author="Unknown", created_by=None)
        second = Book.objects.create(title="Duplicate Legacy Title", lead_author="Unknown", created_by=None)
        migration = importlib.import_module("manager.migrations.0010_backfill_publication_projects")

        migration.backfill_publication_projects(apps, None)
        first.refresh_from_db()
        second.refresh_from_db()

        self.assertIsNotNone(first.project_id)
        self.assertIsNotNone(second.project_id)
        self.assertNotEqual(first.project_id, second.project_id)
        self.assertEqual(first.project.import_key, f"publication:book:{first.id}")
        self.assertIsNone(first.project.created_by_id)
