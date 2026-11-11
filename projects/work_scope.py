from django.contrib.auth import get_user_model
from django.db.models import Q

from projects.models import Project, Task
from projects.scope import scope_projects_for_user
from users.roles import has_role


def assigned_projects_for(user, queryset=None):
    projects = queryset if queryset is not None else Project.objects.all()
    return projects.filter(
        Q(assigned_user=user) | Q(assignments__team_member__user=user)
    ).distinct()


def personal_tasks_for(user, queryset=None):
    """Tasks explicitly assigned to one person, regardless of elevated roles."""
    tasks = queryset if queryset is not None else Task.objects.all()
    if not getattr(user, "is_authenticated", False):
        return tasks.none()
    return tasks.filter(assigned_to=user).distinct()


def workable_tasks_for(user, queryset=None):
    tasks = queryset if queryset is not None else Task.objects.all()
    if not getattr(user, "is_authenticated", False):
        return tasks.none()

    # Staff and authors see only work explicitly assigned to them.
    # Project-level visibility must never reveal another person's task list.
    if not has_role(user, "admin", 'centrehead', 'overseer', "manager", "financialadmin"):
        return personal_tasks_for(user, tasks)

    if has_role(user, "centrehead"):
        from projects.scope import scope_projects_for_user
        return tasks.filter(project__in=scope_projects_for_user(Project.objects.all(), user))

    assigned_projects = assigned_projects_for(user)
    financial_access = Q(project__project_type="financial") if has_role(user, "admin") else Q(pk__in=[])
    return tasks.filter(
        financial_access | Q(assigned_to=user)
        | Q(created_by=user)
        | Q(project__in=assigned_projects)
        | Q(project__created_by=user)
    ).distinct()


def manageable_projects_for(user, queryset=None):
    projects = queryset if queryset is not None else Project.objects.all()
    if has_role(user, "admin"):
        return projects
    if has_role(user, "centrehead"):
        return scope_projects_for_user(projects, user)
    if has_role(user, "manager", "financialadmin"):
        return scope_projects_for_user(projects, user).filter(
            Q(created_by=user)
            | Q(assigned_user=user)
            | Q(assignments__team_member__user=user)
        ).distinct()
    return projects.none()


def can_update_task(user, task):
    if not getattr(user, "is_authenticated", False):
        return False
    return workable_tasks_for(user, Task.objects.filter(pk=task.pk)).exists()


def inspectable_users_for(user):
    users = get_user_model().objects.filter(is_active=True)
    if has_role(user, "centrehead"):
        centre_id = getattr(user, "research_centre_id", None)
        if not centre_id:
            return users.none()
        return users.filter(research_centre_id=centre_id).exclude(role__in=["admin", "dean"])
    if has_role(user, "admin", "dean"):
        return users
    return users.none()


def task_creation_projects_for(user):
    """Project managers manage projects; staff contribute to allocated projects."""
    if has_role(user, 'staff'):
        return assigned_projects_for(user)
    return manageable_projects_for(user)
