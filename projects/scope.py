from django.db.models import Q
from users.roles import has_role


INSTITUTIONAL_ROLES = {'admin', 'dean'}


def user_centre_id(user):
    return getattr(user, 'research_centre_id', None)


def project_centre_q(user_or_centre):
    centre_id = getattr(user_or_centre, 'research_centre_id', None) or getattr(user_or_centre, 'id', None)
    if not centre_id:
        return Q(pk__in=[])

    legacy_links = (
        Q(created_by__research_centre_id=centre_id)
        | Q(assigned_user__research_centre_id=centre_id)
        | Q(assignments__team_member__user__research_centre_id=centre_id)
        | Q(tasks__assigned_to__research_centre_id=centre_id)
        | Q(tasks__created_by__research_centre_id=centre_id)
    )
    return Q(research_centre_id=centre_id) | (Q(research_centre__isnull=True) & legacy_links)


def scope_projects_for_user(queryset, user):
    if has_role(user, *INSTITUTIONAL_ROLES):
        return queryset
    if not user_centre_id(user):
        return queryset.none()
    return queryset.filter(project_centre_q(user)).distinct()


def output_centre_q(user_or_centre):
    centre_id = getattr(user_or_centre, 'research_centre_id', None) or getattr(user_or_centre, 'id', None)
    if not centre_id:
        return Q(pk__in=[])

    return (
        Q(created_by__research_centre_id=centre_id)
        | Q(lead_author_user__research_centre_id=centre_id)
        | Q(co_authors_users__research_centre_id=centre_id)
        | Q(assigned_reviewers__research_centre_id=centre_id)
        | Q(reviewers__research_centre_id=centre_id)
    )


def scope_outputs_for_user(queryset, user):
    if has_role(user, *INSTITUTIONAL_ROLES):
        return queryset
    if not user_centre_id(user):
        return queryset.none()
    return queryset.filter(output_centre_q(user)).distinct()


def scope_books_for_user(queryset, user):
    if has_role(user, *INSTITUTIONAL_ROLES):
        return queryset
    centre_id = user_centre_id(user)
    if not centre_id:
        return queryset.none()
    return queryset.filter(created_by__research_centre_id=centre_id).distinct()


def scope_chapters_for_user(queryset, user):
    """Managers inspect centre books; authors receive only their chapters."""
    if has_role(user, 'admin'):
        return queryset
    if has_role(user, 'centrehead', 'manager'):
        centre_id = user_centre_id(user)
        if not centre_id:
            return queryset.none()
        return queryset.filter(book__created_by__research_centre_id=centre_id).distinct()
    return queryset.filter(assigned_author=user)
