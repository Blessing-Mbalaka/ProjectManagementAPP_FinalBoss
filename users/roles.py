"""Central role/entitlement checks.

The legacy schema stores one primary role.  A project manager who is also a
Django superuser therefore keeps the manager workflow while receiving the
application's admin entitlement (the combination used for Thabile).
"""


def has_role(user, *roles):
    if not getattr(user, "is_authenticated", False) or not getattr(user, "is_active", False):
        return False
    effective = {getattr(user, "role", None)}
    if getattr(user, "is_superuser", False):
        effective.add("admin")
    if getattr(user, 'pk', None):
        group_aliases = {
            'project_manager': 'manager',
            'project-manager': 'manager',
            'project manager': 'manager',
            'centre_head': 'centrehead',
            'centre head': 'centrehead',
            'financial_admin': 'financialadmin',
            'financial admin': 'financialadmin',
        }
        for name in user.groups.values_list('name', flat=True):
            normalized = name.strip().lower()
            effective.add(group_aliases.get(normalized, normalized))
    return bool(effective.intersection(roles))


def can_manage_projects(user):
    return has_role(user, "admin", "centrehead", "manager", "financialadmin")


def can_manage_client_engagements(user):
    return has_role(user, "admin", "centrehead", "manager", "financialadmin")


def can_manage_publications(user):
    # Staff authors (including Raksha), supervisors/professors and project roles
    # may upload; students and finance-only accounts may not.
    return has_role(user, "admin", "centrehead", "manager", "supervisor", "staff")

