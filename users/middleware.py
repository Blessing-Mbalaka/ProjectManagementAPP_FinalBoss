"""Enforce the overseer financial boundary before any view executes."""
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin


class OverseerFinancialBoundaryMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated or request.user.role != 'overseer':
            return None
        if request.POST.get('project_type') == 'financial':
            return HttpResponseForbidden('Overseers cannot create financial projects.')
        name = request.resolver_match.url_name or ''
        route = request.resolver_match.route or ''
        if ('finance' in route or name in {'financial_kanban', 'crm_reporting_data', 'crm_report_export'}
                or (name in {'crm', 'crm_tab'} and view_kwargs.get('tab') in {'financials', 'alerts', 'reports'})):
            return HttpResponseForbidden('Overseers cannot access financial information.')
        return None


class RoleChangeContextMiddleware(MiddlewareMixin):
    def __call__(self, request):
        from .role_security import actor_context
        user = request.user
        context = {'username': user.username if user.is_authenticated else 'Anonymous',
                   'user_id': user.pk if user.is_authenticated else None, 'path': request.path}
        token = actor_context.set(context)
        try:
            return super().__call__(request)
        finally:
            actor_context.reset(token)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != 'POST':
            return None
        name = request.resolver_match.url_name
        registration_attempt = name in {'register', 'register_users'} and request.POST.get('role') in {'admin', 'financialadmin', 'centrehead', 'dean', 'overseer', 'it'}
        if name not in {'edit_user', 'create_user'} and not registration_attempt:
            return None
        from .roles import has_role
        if request.user.is_authenticated and has_role(request.user, 'admin'):
            return None
        from adminpanel.models import SecurityEvent
        from adminpanel.security_service import notify_security_event
        actor = request.user.username if request.user.is_authenticated else 'Anonymous'
        requested = request.POST.get('role', 'account modification')[:64]
        event = SecurityEvent.objects.create(
            user=request.user if request.user.is_authenticated else None, event_type='role_change_attempt',
            severity='high', is_suspicious=True, status='open', path=request.path[:500],
            reason=f'{actor} attempted an unauthorized account role change to {requested}.'[:255],
            details={'actor': actor, 'requested_role': requested, 'target_user_id': view_kwargs.get('user_id'), 'blocked': True},
        )
        notify_security_event(event)
        return HttpResponseForbidden('Only administrators may change account roles.')
