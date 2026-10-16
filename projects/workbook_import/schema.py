from dataclasses import dataclass
from typing import Any


SHEET_NAMES = ("Instructions", "Projects", "Tasks")
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PROJECT_ROWS = 250
MAX_TASK_ROWS = 2_000

PROJECT_COLUMNS = (
    "import_key",
    "project_name",
    "portfolio",
    "description",
    "project_type",
    "project_status",
    "due_date",
    "project_manager_username",
    "research_centre",
    "team_usernames",
    "publication_status",
    "lead_author_username",
    "co_author_usernames",
    "external_authors",
    "reviewer_usernames",
    "publisher",
    "total_chapters",
    "completed_chapters",
    "internal_external",
    "paper_type",
    "version",
    "abstract",
    "target_journal",
    "conference_name",
    "conference_date",
    "location",
    "submission_date",
    "decision_date",
)

TASK_COLUMNS = (
    "project_name",
    "task_name",
    "parent_task",
    "assigned_to",
    "responsibility",
    "status",
    "priority",
    "task_type",
    "due_date",
    "comments",
)


@dataclass(frozen=True)
class WorkbookCellError:
    sheet: str
    row: int | None
    field: str
    message: str


@dataclass(frozen=True)
class WorkbookReadResult:
    project_rows: tuple[dict[str, Any], ...] = ()
    task_rows: tuple[dict[str, Any], ...] = ()
    errors: tuple[WorkbookCellError, ...] = ()

    @property
    def is_valid(self):
        return not self.errors
