import hashlib
import ipaddress
import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from users.models import CustomUser

from .models import Notification, SecurityEvent


logger = logging.getLogger(__name__)


def client_ip(request):
    """Return a validated client address without trusting malformed proxy input."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    candidates = [part.strip() for part in forwarded.split(',') if part.strip()]
    candidates.append(request.META.get('REMOTE_ADDR', ''))
    for candidate in candidates:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return None


def masked_ip(value):
    if not value:
        return 'Unavailable'
    address = ipaddress.ip_address(value)
    if address.version == 4:
        parts = value.split('.')
        return '.'.join(parts[:2] + ['x', 'x'])
    return f'{address.exploded.split(":")[0]}:{address.exploded.split(":")[1]}:…'


def device_label(user_agent):
    value = (user_agent or '').lower()
    if 'edg/' in value:
        browser = 'Microsoft Edge'
    elif 'chrome/' in value:
        browser = 'Chrome'
    elif 'firefox/' in value:
        browser = 'Firefox'
    elif 'safari/' in value:
        browser = 'Safari'
    else:
        browser = 'Unidentified browser'
    device = 'mobile device' if any(token in value for token in ('mobile', 'android', 'iphone')) else 'computer'
    return f'{browser} on a {device}'


def is_unusual_login_time(moment=None):
    local = timezone.localtime(moment or timezone.now())
    start = int(getattr(settings, 'SECURITY_SUSPICIOUS_LOGIN_START_HOUR', 0))
    end = int(getattr(settings, 'SECURITY_SUSPICIOUS_LOGIN_END_HOUR', 5))
    if start == end:
        return True
    if start < end:
        return start <= local.hour < end
    return local.hour >= start or local.hour < end


def _security_recipients(user=None):
    queryset = CustomUser.objects.filter(is_active=True).filter(
        Q(role='admin') | Q(is_superuser=True)
    )
    if user and user.research_centre_id:
        queryset = queryset | CustomUser.objects.filter(
            is_active=True,
            role='centrehead',
            research_centre_id=user.research_centre_id,
        )
    return queryset.distinct()


def _create_notification(title, body, recipients, priority='high'):
    recipient_ids = list(recipients.values_list('id', flat=True))
    if not recipient_ids:
        return None
    notification = Notification.objects.create(
        title=title,
        body=body,
        priority=priority,
        audience='specific',
        is_pinned=priority == 'urgent',
    )
    notification.recipients.set(recipient_ids)
    return notification


def notify_security_event(event):
    local_time = timezone.localtime(event.occurred_at).strftime('%d %b %Y at %H:%M')
    if event.user:
        _create_notification(
            'Was this you? Security activity detected',
            f'{event.reason} on {local_time}. Open Account Security to confirm it or secure your account.',
            CustomUser.objects.filter(pk=event.user_id),
            priority='urgent' if event.severity == 'high' else 'high',
        )
    administrators = _security_recipients(event.user)
    if event.user_id:
        administrators = administrators.exclude(pk=event.user_id)
    _create_notification(
        f'Security flag: {event.get_event_type_display()}',
        f'{event.user.username if event.user else "Unknown visitor"}: {event.reason} ({local_time}).',
        administrators,
        priority='urgent' if event.severity == 'high' else 'high',
    )


def record_login(request, user):
    unusual = is_unusual_login_time()
    event = SecurityEvent.objects.create(
        user=user,
        event_type='login',
        severity='high' if unusual else 'low',
        status='open' if unusual else 'confirmed',
        is_suspicious=unusual,
        reason='Login during unusual hours (midnight to 05:00)' if unusual else 'Successful login',
        ip_address=client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        reviewed_at=None if unusual else timezone.now(),
    )
    if unusual:
        request.session['pending_security_event_id'] = event.id
        notify_security_event(event)
    return event


def _increment_counter(key, timeout):
    if cache.add(key, 1, timeout=timeout):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1


def record_failed_login(request, username):
    window = int(getattr(settings, 'SECURITY_FAILED_LOGIN_WINDOW_SECONDS', 600))
    limit = int(getattr(settings, 'SECURITY_FAILED_LOGIN_LIMIT', 5))
    ip = client_ip(request)
    identity = hashlib.sha256(f'{username.lower()}|{ip}'.encode()).hexdigest()
    count = _increment_counter(f'security:failed:{identity}', window)
    if count < limit or not cache.add(f'security:failed-alert:{identity}', 1, timeout=window):
        return None
    user = CustomUser.objects.filter(username__iexact=username, is_active=True).first()
    event = SecurityEvent.objects.create(
        user=user,
        event_type='failed_login_burst',
        severity='high',
        status='open',
        is_suspicious=True,
        reason=f'{count} failed login attempts within {window // 60} minutes',
        ip_address=ip,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        request_count=count,
    )
    notify_security_event(event)
    return event


def record_denied_access(request, status_code=403):
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        return None
    cooldown = int(getattr(settings, 'SECURITY_ACCESS_ALERT_COOLDOWN_SECONDS', 900))
    identity = hashlib.sha256(f'{user.pk}|{request.path}'.encode()).hexdigest()
    if not cache.add(f'security:denied:{identity}', 1, timeout=cooldown):
        return None
    event = SecurityEvent.objects.create(
        user=user,
        event_type='access_denied',
        severity='medium',
        status='open',
        is_suspicious=True,
        reason=(
            'Attempted to open a page outside the account permissions'
            if status_code == 403
            else 'Requested a protected record that was unavailable or outside the account permissions'
        ),
        path=request.path[:500],
        ip_address=client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )
    notify_security_event(event)
    return event


def monitor_request_volume(request):
    window = int(getattr(settings, 'SECURITY_REQUEST_WINDOW_SECONDS', 60))
    limit = int(getattr(settings, 'SECURITY_REQUEST_LIMIT', 120))
    user = getattr(request, 'user', None)
    actor = f'user:{user.pk}' if getattr(user, 'is_authenticated', False) else f'ip:{client_ip(request)}'
    identity = hashlib.sha256(actor.encode()).hexdigest()
    count = _increment_counter(f'security:requests:{identity}', window)
    if count < limit or not cache.add(f'security:request-alert:{identity}', 1, timeout=window * 5):
        return None
    event = SecurityEvent.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        event_type='request_burst',
        severity='high',
        status='open',
        is_suspicious=True,
        reason=f'Unusual request volume: {count} requests within {window} seconds',
        path=request.path[:500],
        ip_address=client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        request_count=count,
    )
    notify_security_event(event)
    return event


def safe_monitor(callable_, *args):
    """Security telemetry must never make the requested page fail."""
    try:
        return callable_(*args)
    except Exception:
        logger.exception('Security monitoring failed in %s', getattr(callable_, '__name__', 'monitor'))
        return None
