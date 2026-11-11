"""Return saves to an authorised page in the originating feature."""
from urllib.parse import parse_qs, urlsplit, urlunsplit

from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .roles import can_manage_projects, can_manage_publications, has_role


def role_home_name(user):
    return {'it': 'it_dashboard', 'admin': 'overview', 'dean': 'overview', 'centrehead': 'overview', 'overseer': 'overview', 'supervisor': 'supervisor_dashboard_portal', 'manager': 'manager_dashboard', 'financialadmin': 'finance', 'student': 'student_dashboard'}.get(user.role, 'dashboard')


def workspace_base(user):
    if user.role in {'admin', 'dean', 'centrehead', 'overseer', 'financialadmin', 'it'}:
        return 'adminpanel/index.html'
    if user.role == 'manager':
        return 'manager/home.html'
    if user.role == 'supervisor':
        return 'supervisors/base.html'
    return 'base.html'


def personal_projects_name(user):
    return 'staff_projects' if user.role in {'staff', 'student', 'supervisor'} else 'my_projects'


def task_board_name(user):
    if user.role == 'financialadmin':
        return 'financial_kanban'
    return 'manager_kanban' if user.role in {'admin', 'centrehead', 'overseer', 'manager'} else 'staff_kanban'


def paper_workspace_name(user):
    return 'admin_journal' if user.role in {'admin', 'dean', 'centrehead', 'overseer'} else 'manager_journal'


FAMILIES = {
    'tasks': {'project_tasks', 'staff_projects', 'staff_kanban', 'my_projects', 'manager_kanban', 'financial_kanban', 'assign_projects', 'admin_my_projects'},
    'projects': {'assign_projects', 'staff_projects', 'my_projects', 'admin_my_projects', 'overview', 'manager_dashboard', 'dashboard'},
    'papers': {'admin_journal', 'manager_journal'},
    'books': {'admin_book', 'manager_book'},
    'learning': {'manager_elearning', 'staff_elearning'},
    'templates': {'manager_templates', 'staff_templates', 'communique_section'},
    'finance': {'finance', 'finance_section', 'finance_readonly', 'finance_readonly_section'},
    'communique': {'communique', 'communique_section'},
    'home': {'overview', 'manager_dashboard', 'dashboard', 'finance', 'it_dashboard', 'supervisor_dashboard_portal', 'student_dashboard'},
}


def workspace_return_url(request, fallback, *, family, project=None):
    """Accept an explicit form return URL or Referer, never an arbitrary URL.

    Return targets are GET pages in the same feature, checked against role and
    project scope. Permissions remain independent of the primary role's layout.
    """
    fallback = fallback if fallback.startswith('/') else reverse(fallback)
    for candidate in [request.POST.get('return_to', ''), request.META.get('HTTP_REFERER', '')]:
        if not candidate or len(candidate) > 2048 or not url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            continue
        try:
            parts = urlsplit(candidate)
            if not parts.path.startswith('/') or parts.path.startswith('//'):
                continue
            match = resolve(parts.path)
        except (ValueError, Resolver404):
            continue
        name = match.url_name
        if name not in FAMILIES[family]:
            continue
        user = request.user
        if family == 'home' and name != role_home_name(user):
            continue
        if name in {'my_projects', 'assign_projects'} and not can_manage_projects(user):
            continue
        if name == 'admin_my_projects' and user.role != 'admin':
            continue
        if name == 'manager_kanban' and user.role == 'financialadmin':
            continue
        if name == 'manager_kanban' and not can_manage_projects(user):
            continue
        if name == 'financial_kanban':
            if user.role == 'overseer' or not has_role(user, 'admin', 'centrehead', 'financialadmin'):
                continue
            selected = parse_qs(parts.query).get('assignee', [''])[0]
            if selected and (not selected.isdecimal() or not has_role(user, 'admin')):
                continue
        if name == 'project_tasks':
            from projects.work_scope import task_creation_projects_for
            project_id = match.kwargs['project_id']
            if project is not None and project_id != project.pk:
                continue
            if not task_creation_projects_for(user).filter(pk=project_id).exists():
                continue
        if name == 'assign_projects':
            selected = parse_qs(parts.query).get('project_id', [''])[0]
            if selected:
                from projects.work_scope import manageable_projects_for
                if not selected.isdecimal() or not manageable_projects_for(user).filter(pk=selected).exists():
                    continue
        if name in {'overview', 'manager_dashboard', 'dashboard'} and name != role_home_name(user):
            continue
        if family in {'papers', 'books'} and not can_manage_publications(user):
            continue
        if name in {'admin_journal', 'admin_book'} and user.role not in {'admin', 'dean', 'centrehead', 'overseer'}:
            continue
        if name == 'communique_section' and match.kwargs.get('section') not in {'templates', 'messages', 'availability'}:
            continue
        if family == 'templates' and name == 'communique_section' and match.kwargs.get('section') != 'templates':
            continue
        if name in {'finance', 'finance_section'} and user.role not in {'admin', 'centrehead', 'financialadmin'}:
            continue
        if name in {'finance_readonly', 'finance_readonly_section'} and user.role not in {'admin', 'centrehead', 'financialadmin', 'dean'}:
            continue
        return urlunsplit(('', '', parts.path, parts.query, parts.fragment))
    return fallback
