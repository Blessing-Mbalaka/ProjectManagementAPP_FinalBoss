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
