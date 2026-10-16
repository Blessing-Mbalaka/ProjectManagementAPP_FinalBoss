from django.db import transaction

from manager.models import Book, Conference, Paper
from projects.models import Project


STATUS_MAPS = {
    Book: {
        'published': 'completed',
        'writing': 'in-progress',
        'submission': 'in-progress',
        'review': 'in-progress',
        'production': 'in-progress',
    },
    Paper: {
        'draft': 'planning',
        'published': 'completed',
        'rejected': 'on-hold',
    },
    Conference: {
        'draft': 'planning',
        'presented': 'completed',
        'rejected': 'on-hold',
    },
}


def _project_type(publication):
    if isinstance(publication, Book):
        return 'book'
    if isinstance(publication, Paper):
        return 'paper'
    if isinstance(publication, Conference):
        return 'conference'
    raise TypeError(f'Unsupported publication type: {type(publication).__name__}')


def _project_status(publication):
    mapping = STATUS_MAPS[type(publication)]
    return mapping.get(publication.status, 'in-progress')


@transaction.atomic
def sync_publication_project(
    publication,
    *,
    actor,
    manager=None,
    research_centre=None,
    project_values=None,
):
    project = publication.project if publication.project_id else Project()
    project.name = publication.title
    description = getattr(publication, 'description', None) or getattr(publication, 'abstract', None) or ''
    project.description = description[:255]
    project.project_type = _project_type(publication)
    project.status = _project_status(publication)
    project.due_date = getattr(publication, 'due_date', None) or getattr(publication, 'conference_date', None)
    project.created_by = project.created_by or actor or getattr(publication, 'created_by', None)
    if manager is not None:
        project.assigned_user = manager
    if research_centre is not None:
        project.research_centre = research_centre
    elif project.research_centre_id is None and project.created_by_id:
        project.research_centre = getattr(project.created_by, 'research_centre', None)
    if not project.import_key:
        project.import_key = f'publication:{_project_type(publication)}:{publication.pk}'
    for field, value in (project_values or {}).items():
        if field not in {'name', 'description', 'status', 'due_date', 'portfolio'}:
            raise ValueError(f'Unsupported project override: {field}')
        setattr(project, field, value)
    project.save()
    if publication.project_id != project.id:
        publication.project = project
        publication.save(update_fields=['project'])
    return project
