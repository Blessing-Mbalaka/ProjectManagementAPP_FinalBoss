from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from projects.workbook_import.application import apply_workbook_preview
from projects.workbook_import.validation import validate_workbook
from projects.workbook_import.workbook import read_workbook


User = get_user_model()


def _format_issue(issue):
    location = issue.sheet
    if issue.row:
        location += f" row {issue.row}"
    if issue.field:
        location += f", {issue.field}"
    return f"{location}: {issue.message}"


class Command(BaseCommand):
    help = "Validate and import a combined project workbook."

    def add_arguments(self, parser):
        parser.add_argument("workbook_path")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = options["workbook_path"]
        try:
            with open(path, "rb") as handle:
                read_result = read_workbook(File(handle, name=path))
        except OSError as exc:
            raise CommandError(f"Workbook not found or unreadable: {path}") from exc

        preferred_username = ""
        if read_result.project_rows:
            preferred_username = str(read_result.project_rows[0].get("project_manager_username") or "").strip()
        actor = (
            User.objects.filter(is_active=True, role__in=["admin", "dean"]).first()
            or User.objects.filter(is_active=True, username=preferred_username).first()
            or User.objects.filter(is_active=True, role__in=["manager", "centrehead"]).first()
        )
        if actor is None:
            raise CommandError("No active project-management user is available to authorize this import.")

        preview = validate_workbook(read_result, actor=actor)
        for issue in preview.issues:
            self.stdout.write(_format_issue(issue))
        if preview.errors:
            raise CommandError(_format_issue(preview.errors[0]))

        creates = sum(action.operation == "create" for action in preview.actions)
        updates = sum(action.operation == "update" for action in preview.actions)
        self.stdout.write(f"Creates: {creates}; Updates: {updates}; Warnings: {len(preview.warnings)}")
        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No records written."))
            return

        result = apply_workbook_preview(preview, actor=actor)
        self.stdout.write(self.style.SUCCESS(
            f"Projects created: {result.created_projects}; Projects updated: {result.updated_projects}; "
            f"Tasks created: {result.created_tasks}; Tasks updated: {result.updated_tasks}."
        ))
