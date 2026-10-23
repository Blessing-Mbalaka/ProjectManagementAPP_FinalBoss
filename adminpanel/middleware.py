import logging

from django.db import DatabaseError

from adminpanel.models import PageVisitLog
from adminpanel.security_service import monitor_request_volume, record_denied_access, safe_monitor


logger = logging.getLogger(__name__)


class PageVisitAuditMiddleware:
    """Log successful authenticated page views without query strings or form data."""

    EXCLUDED_PREFIXES = (
        '/static/',
        '/media/',
        '/test_media/',
        '/adminpanel/api/',
        '/api/',
    )
    EXCLUDED_PATHS = {'/favicon.ico'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(('/static/', '/media/', '/test_media/')):
            safe_monitor(monitor_request_volume, request)
        response = self.get_response(request)
        resolver_match = getattr(request, 'resolver_match', None)
        if response.status_code == 403 or (response.status_code == 404 and resolver_match is not None):
            safe_monitor(record_denied_access, request, response.status_code)
        self._record(request, response)
        return response

    def _record(self, request, response):
        user = getattr(request, 'user', None)
        path = request.path
        if (
            request.method != 'GET'
            or not getattr(user, 'is_authenticated', False)
            or response.status_code >= 400
            or path in self.EXCLUDED_PATHS
            or path.startswith(self.EXCLUDED_PREFIXES)
            or 'text/html' not in response.get('Content-Type', '')
        ):
            return

        resolver_match = getattr(request, 'resolver_match', None)
        try:
            PageVisitLog.objects.create(
                user=user,
                path=path[:500],
                view_name=(resolver_match.view_name if resolver_match else '')[:160],
                method=request.method,
            )
        except DatabaseError:
            # Activity auditing must never make the page the user requested fail.
            logger.exception('Unable to record page visit for %s', path)
