from django.contrib.auth import get_user_model
from django.db.models import Q

from projects.models import Project, Task


def assigned_projects_for(user, queryset=None):
    projects = queryset if queryset is not None else Project.objects.all()
    return projects.filter(
        Q(assigned_user=user) | Q(assignments__team_member__user=user)
    ).distinct()


def workable_tasks_for(user, queryset=None):
    tasks = queryset if queryset is not None else Task.objects.all()
    assigned_projects = assigned_projects_for(user)
    return tasks.filter(
        Q(assigned_to=user)
        | Q(created_by=user)
        | Q(project__in=assigned_projects)
    ).distinct()


def can_update_task(user, task):
    if not getattr(user, "is_authenticated", False):
        return False
    return workable_tasks_for(user, Task.objects.filter(pk=task.pk)).exists()


def inspectable_users_for(user):
    users = get_user_model().objects.filter(is_active=True)
    if getattr(user, "role", None) == "centrehead":
        centre_id = getattr(user, "research_centre_id", None)
        if not centre_id:
            return users.none()
        return users.filter(research_centre_id=centre_id).exclude(role__in=["admin", "dean"])
    if getattr(user, "role", None) in {"admin", "dean"}:
        return users
    return users.none()
