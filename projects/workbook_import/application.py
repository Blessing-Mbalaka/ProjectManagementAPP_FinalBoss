from dataclasses import dataclass
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction

from adminpanel.models import ResearchCentre
from manager.models import Book, Conference, Paper
from manager.publication_projects import sync_publication_project
from projects.models import Assignment, Project, Task, TeamMember

from .validation import WorkbookImportPreview, _can_manage_existing, normalize_name


User = get_user_model()


class WorkbookImportError(ValueError):
    pass


@dataclass(frozen=True)
class ImportResult:
    created_projects: int
    updated_projects: int
    created_tasks: int
    updated_tasks: int
    affected_project_ids: tuple[int, ...]
    warnings: tuple[str, ...]


def _date(value):
    return date.fromisoformat(value) if value else None


def _display_name(user):
    return user.get_full_name() or user.username if user else ""


def _ensure_membership(project, user_id, responsibility):
    user = User.objects.get(pk=user_id)
    member, _ = TeamMember.objects.get_or_create(
        user=user,
        defaults={"full_name": _display_name(user), "role": user.get_role_display()},
    )
    Assignment.objects.get_or_create(
        project=project,
        team_member=member,
        defaults={"responsibility": responsibility},
    )


def _save_publication(project, row, actor):
    if row.project_type == "software":
        return
    manager = User.objects.get(pk=row.manager_id)
    centre = ResearchCentre.objects.get(pk=row.centre_id)
    lead = User.objects.filter(pk=row.lead_author_id).first()
    project_values = {
        "name": row.name,
        "description": row.description,
        "status": row.project_status,
        "due_date": _date(row.due_date),
        "portfolio": row.portfolio,
    }

    if row.project_type == "book":
        publication = Book.objects.filter(project=project).first() or Book(project=project)
        publication.description = row.description
        publication.due_date = _date(row.due_date)
        publication.publisher = row.publisher
        publication.total_chapters = row.total_chapters
        publication.completed_chapters = row.completed_chapters
        publication.lead_author_user = lead
    elif row.project_type == "paper":
        publication = Paper.objects.filter(project=project).first() or Paper(project=project, manuscript="")
        publication.paper_type = row.paper_type
        publication.internal_external = row.internal_external
        publication.version = row.version
        publication.abstract = row.abstract
        publication.target_journal = row.target_journal
        publication.submission_date = _date(row.submission_date)
        publication.decision_date = _date(row.decision_date)
        publication.lead_author_user = lead
    else:
        publication = Conference.objects.filter(project=project).first() or Conference(project=project)
        publication.internal_external = row.internal_external
        publication.conference_name = row.conference_name
        publication.location = row.location
        publication.abstract = row.abstract
        publication.submission_date = _date(row.submission_date)
        publication.conference_date = _date(row.conference_date)
        publication.decision_date = _date(row.decision_date)
        publication.lead_author_user = lead

    publication.title = row.name
    publication.status = row.publication_status
    publication.lead_author = _display_name(lead)
    publication.external_authors = list(row.external_authors)
    publication.created_by = publication.created_by or lead or manager or actor
    publication.save()
    publication.co_authors_users.set(row.co_author_ids)
    if isinstance(publication, (Paper, Conference)):
        publication.assigned_reviewers.set(row.reviewer_ids)
    sync_publication_project(
        publication,
        actor=actor,
        manager=manager,
        research_centre=centre,
        project_values=project_values,
    )


def _save_tasks(preview, project_by_key, actor):
    created_count = 0
    updated_count = 0
    saved = {}
    for row in preview.tasks:
        project = project_by_key[row.project_import_key]
        task = Task.objects.filter(pk=row.existing_task_id, project=project).first() if row.existing_task_id else None
        if task is None:
            task = Task.objects.filter(project=project, import_key=row.import_key).first()
        created = task is None
        task = task or Task(project=project, import_key=row.import_key)
        task.import_key = row.import_key
        task.title = row.title
        task.assigned_to_id = row.assigned_to_id
        task.status = row.status
        task.priority = row.priority or None
        task.task_type = row.task_type or None
        task.due_date = _date(row.due_date)
        task.comments = row.comments
        task.created_by = task.created_by or actor
        task.parent_task = None
        task.save()
        saved[(row.project_import_key, row.normalized_name)] = task
        created_count += int(created)
        updated_count += int(not created)
        if row.assigned_to_id:
            _ensure_membership(project, row.assigned_to_id, row.responsibility or "Task assignee")

    for row in preview.tasks:
        if not row.parent_normalized:
            continue
        task = saved[(row.project_import_key, row.normalized_name)]
        parent = saved.get((row.project_import_key, row.parent_normalized))
        if parent is None:
            project = project_by_key[row.project_import_key]
            parent = next(
                item for item in project.tasks.exclude(pk=task.pk)
                if normalize_name(item.title) == row.parent_normalized
            )
        task.parent_task = parent
        task.save(update_fields=["parent_task"])
    return created_count, updated_count


@transaction.atomic
def apply_workbook_preview(preview: WorkbookImportPreview, *, actor) -> ImportResult:
    if preview.actor_id != actor.id:
        raise PermissionDenied("This workbook preview belongs to another user.")
    if preview.errors:
        raise WorkbookImportError("A workbook with validation errors cannot be applied.")

    created_projects = 0
    updated_projects = 0
    project_by_key = {}
    for row in preview.projects:
        existing = Project.objects.select_for_update().filter(import_key=row.import_key).first()
        if existing and not _can_manage_existing(actor, existing):
            raise PermissionDenied(f'You are no longer authorized to update project "{existing.name}".')
        manager = User.objects.get(pk=row.manager_id)
        centre = ResearchCentre.objects.get(pk=row.centre_id)
        project, created = Project.objects.update_or_create(
            import_key=row.import_key,
            defaults={
                "name": row.name,
                "portfolio": row.portfolio,
                "description": row.description,
                "project_type": row.project_type,
                "status": row.project_status,
                "due_date": _date(row.due_date),
                "assigned_user": manager,
                "created_by": existing.created_by if existing and existing.created_by_id else manager,
                "research_centre": centre,
            },
        )
        project_by_key[row.import_key] = project
        created_projects += int(created)
        updated_projects += int(not created)
        _save_publication(project, row, actor)

        for user_id in row.team_user_ids:
            _ensure_membership(project, user_id, "Team member")
        contributor_ids = set(row.co_author_ids) | set(row.reviewer_ids)
        if row.lead_author_id:
            contributor_ids.add(row.lead_author_id)
        for user_id in contributor_ids:
            _ensure_membership(project, user_id, "Publication contributor")

    created_tasks, updated_tasks = _save_tasks(preview, project_by_key, actor)
    return ImportResult(
        created_projects=created_projects,
        updated_projects=updated_projects,
        created_tasks=created_tasks,
        updated_tasks=updated_tasks,
        affected_project_ids=tuple(project.id for project in project_by_key.values()),
        warnings=tuple(issue.message for issue in preview.warnings),
    )
