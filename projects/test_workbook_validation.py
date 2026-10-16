from django.contrib.auth import get_user_model
from django.test import TestCase

from adminpanel.models import ResearchCentre
from manager.models import Book
from projects.models import Project, Task
from projects.workbook_import.schema import WorkbookReadResult
from projects.workbook_import.validation import task_import_key, validate_workbook


User = get_user_model()


class WorkbookValidationTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Digital Research")
        self.other_centre = ResearchCentre.objects.create(name="Other Centre")
        self.manager = User.objects.create_user(
            username="manager1",
            role="manager",
            research_centre=self.centre,
        )
        self.alice = User.objects.create_user(
            username="alice",
            role="staff",
            research_centre=self.centre,
        )
        self.bob = User.objects.create_user(
            username="bob",
            role="staff",
            research_centre=self.centre,
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            role="staff",
            research_centre=self.other_centre,
        )

    def project_row(self, **overrides):
        row = {
            "_row": 2,
            "import_key": "website-001",
            "project_name": "Website Redesign",
            "portfolio": "Digital Projects",
            "description": "Refresh the website",
            "project_type": "software",
            "project_status": "planning",
            "due_date": "2027-03-31",
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
        row.update(overrides)
        return row

    def task_row(self, name, **overrides):
        row = {
            "_row": 2,
            "project_name": "Website Redesign",
            "task_name": name,
            "parent_task": "",
            "assigned_to": "",
            "responsibility": "",
            "status": "todo",
            "priority": "Medium",
            "task_type": "Frontend",
            "due_date": "2027-02-28",
            "comments": "",
        }
        row.update(overrides)
        return row

    def preview(self, projects, tasks=()):
        return validate_workbook(
            WorkbookReadResult(project_rows=tuple(projects), task_rows=tuple(tasks)),
            actor=self.manager,
        )

    def test_valid_software_preview_resolves_out_of_order_tree_and_membership(self):
        preview = self.preview(
            [self.project_row(team_usernames="alice")],
            [
                self.task_row("Create homepage", _row=2, parent_task="Build frontend", assigned_to="bob"),
                self.task_row("Build frontend", _row=3, assigned_to="alice"),
            ],
        )

        self.assertTrue(preview.is_valid)
        self.assertEqual(preview.projects[0].portfolio, "Digital Projects")
        child = next(task for task in preview.tasks if task.title == "Create homepage")
        self.assertEqual(child.parent_name, "Build frontend")
        self.assertEqual(child.import_key, task_import_key("Create homepage"))
        self.assertTrue(any(
            action.category == "membership" and action.label == "bob"
            for action in preview.actions
        ))
        self.assertFalse(Project.objects.exists())

    def test_publication_authors_are_normalized_and_unknown_users_warn(self):
        kinds = [
            self.project_row(
                _row=2,
                import_key="book-1",
                project_name="Book One",
                project_type="book",
                publication_status="writing",
                lead_author_username="alice",
                co_author_usernames="bob;missing-author;outsider",
                external_authors=" Dr Jane Doe ;dr jane doe; Prof John Roe ",
                publisher="Publisher",
                total_chapters="10",
                completed_chapters="2",
            ),
            self.project_row(
                _row=3,
                import_key="paper-1",
                project_name="Paper One",
                project_type="paper",
                publication_status="draft",
                lead_author_username="alice",
                co_author_usernames="bob",
                internal_external="internal",
                paper_type="journal",
                version="1.0",
            ),
            self.project_row(
                _row=4,
                import_key="conference-1",
                project_name="Conference One",
                project_type="conference",
                publication_status="draft",
                lead_author_username="alice",
                internal_external="internal",
                conference_name="Annual Conference",
            ),
        ]

        preview = self.preview(kinds)

        self.assertTrue(preview.is_valid)
        book = next(row for row in preview.projects if row.project_type == "book")
        self.assertEqual(book.external_authors, ("Dr Jane Doe", "Prof John Roe"))
        self.assertEqual(book.co_author_ids, (self.bob.id,))
        self.assertEqual(len(preview.warnings), 2)
        self.assertTrue(all(issue.field == "co_author_usernames" for issue in preview.warnings))

    def test_normalized_duplicate_names_and_blank_external_author_update_are_visible(self):
        project = Project.objects.create(
            import_key="book-existing",
            name="Existing Book",
            project_type="book",
            status="planning",
            created_by=self.manager,
            assigned_user=self.manager,
            research_centre=self.centre,
        )
        Book.objects.create(
            title="Existing Book",
            lead_author="",
            status="writing",
            external_authors=["Old External"],
            created_by=self.manager,
            project=project,
        )
        Task.objects.create(project=project, title="Existing Parent")
        row = self.project_row(
            import_key="book-existing",
            project_name="Existing Book",
            project_type="book",
            publication_status="writing",
            external_authors="",
        )

        preview = self.preview([row], [self.task_row("Child", project_name="Existing Book", parent_task=" existing parent ")])

        self.assertTrue(preview.is_valid)
        self.assertTrue(any("external authors" in action.label.lower() for action in preview.actions))

        duplicate = self.preview(
            [self.project_row(), self.project_row(_row=3, import_key="website-002", project_name=" website redesign ")],
            [self.task_row("Plan"), self.task_row(" plan ", _row=3)],
        )
        self.assertTrue(any(issue.field == "project_name" for issue in duplicate.errors))
        self.assertTrue(any(issue.field == "task_name" for issue in duplicate.errors))

    def test_unknown_blocking_identities_and_cross_centre_assignment_are_errors(self):
        preview = self.preview(
            [self.project_row(project_manager_username="missing", team_usernames="missing-team")],
            [self.task_row("Task", assigned_to="outsider")],
        )

        self.assertFalse(preview.is_valid)
        self.assertTrue(any(issue.field == "project_manager_username" for issue in preview.errors))
        self.assertTrue(any(issue.field == "team_usernames" for issue in preview.errors))
        self.assertTrue(any(issue.field == "assigned_to" for issue in preview.errors))

    def test_invalid_task_graph_reports_missing_self_and_cycle(self):
        preview = self.preview(
            [self.project_row()],
            [
                self.task_row("Missing child", _row=2, parent_task="Unknown"),
                self.task_row("Self", _row=3, parent_task="Self"),
                self.task_row("Cycle A", _row=4, parent_task="Cycle B"),
                self.task_row("Cycle B", _row=5, parent_task="Cycle A"),
            ],
        )

        messages = " ".join(issue.message.lower() for issue in preview.errors)
        self.assertIn("not found", messages)
        self.assertIn("own parent", messages)
        self.assertIn("cycle", messages)

    def test_conditional_publication_and_value_errors_include_location(self):
        preview = self.preview([
            self.project_row(
                project_type="software",
                publication_status="draft",
                due_date="31/03/2027",
            ),
            self.project_row(
                _row=3,
                import_key="book-bad",
                project_name="Bad Book",
                project_type="book",
                publication_status="writing",
                total_chapters="2",
                completed_chapters="3",
            ),
            self.project_row(
                _row=4,
                import_key="conference-bad",
                project_name="Bad Conference",
                project_type="conference",
                publication_status="draft",
                internal_external="internal",
                conference_name="",
            ),
        ])

        self.assertFalse(preview.is_valid)
        self.assertTrue(all(issue.sheet == "Projects" and issue.row for issue in preview.errors))
        fields = {issue.field for issue in preview.errors}
        self.assertTrue({"publication_status", "due_date", "completed_chapters", "conference_name"} <= fields)
