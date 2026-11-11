"""Weekly, private account check-ins using the actual latest login timestamp."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.db.models import Q
from django.db import connections, InterfaceError, OperationalError
from django.utils import timezone

from adminpanel.email_health import configuration_problem, update_email_status
from adminpanel.security_service import _create_notification
from .models import LoginPingDelivery


def _database_operation(operation):
    """Retry idempotent DB work once; never repeat an SMTP send."""
    try:
        return operation()
    except (InterfaceError, OperationalError):
        connections['default'].close()
        return operation()


def ping_body(user, now):
    today = timezone.localtime(now).date()
    name = user.first_name.strip() or user.username
    if user.last_login:
        login_date = timezone.localtime(user.last_login).date()
        days = max(0, (today - login_date).days)
        if days == 0:
            activity = 'You last logged in today (' + login_date.strftime('%d %B %Y') + '). This is your weekly check-in.'
            request = 'Please continue checking in regularly so we know how you are doing.'
        else:
            activity = f"You have not logged in for {days} {'day' if days == 1 else 'days'}. Your last login was on {login_date:%d %B %Y}."
            request = 'Please log in when you can. We are getting concerned and would like to know how you are doing.'
    else:
        days = max(0, (today - timezone.localtime(user.date_joined).date()).days)
        activity = f"You have not logged in yet. Your account was created {days} {'day' if days == 1 else 'days'} ago."
        request = 'Please log in when you can. We are getting concerned and would like to know how you are doing.'
    return f'Hi {name},\n\n{activity}\n\n{request}\n\nProject Management Team\n'


def run_weekly_login_pings(now=None):
    """Optional existing-worker schedule: Mondays from 09:00 in app timezone."""
    if not settings.LOGIN_PINGS_ENABLED:
        return None
    now = now or timezone.now()
    local = timezone.localtime(now)
    if local.weekday() != 0 or local.hour < 9:
        return None
    # A partial/uncertain run needs operator review, rather than retries every
    # worker tick. The manual command can send only the unreserved remainder.
    if LoginPingDelivery.objects.filter(week_start=local.date()).exists():
        return None
    return send_login_pings(send=True, now=now)


def send_login_pings(*, send=False, now=None):
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    week_start = today - timedelta(days=today.weekday())
    if send and configuration_problem():
        update_email_status('not_configured')
        raise ValueError('SMTP is not configured for delivery. No login check-ins were sent; IT has been notified.')
    result = dict(active=0, eligible=0, already_processed=0, invalid_email=0, accepted=0, failed=0, uncertain=0, not_attempted=0)
    # Do not hold a server-side database cursor open across SMTP calls.
    users = _database_operation(lambda: list(get_user_model().objects.filter(is_active=True).only('pk', 'username', 'first_name', 'email', 'last_login', 'date_joined').order_by('pk')))
    stopped = False
    for user in users:
        result['active'] += 1
        try:
            validate_email(user.email)
        except ValidationError:
            result['invalid_email'] += 1
            continue
        if _database_operation(lambda: LoginPingDelivery.objects.filter(user=user, week_start=week_start).exists()):
            result['already_processed'] += 1
            continue
        result['eligible'] += 1
        if not send:
            continue
        if stopped:
            result['not_attempted'] += 1
            continue
        delivery, created = _database_operation(lambda: LoginPingDelivery.objects.get_or_create(user=user, week_start=week_start))
        if not created:
            result['already_processed'] += 1
            result['eligible'] -= 1
            continue
        # Commit the reservation before SMTP. A crashed/uncertain attempt is never
        # automatically resent: SMTP and the database cannot commit atomically.
        message = EmailMessage('A quick check-in from Project Management', ping_body(user, now), settings.DEFAULT_FROM_EMAIL, [user.email])
        try:
            sent = message.send(fail_silently=False)
        except Exception:
            # Avoid recording provider responses that could expose credentials.
            delivery.status = 'uncertain'
            result['uncertain'] += 1
            stopped = True
        else:
            if sent == 1:
                delivery.status = 'accepted'
                delivery.accepted_at = timezone.now()
                result['accepted'] += 1
            else:
                delivery.status = 'failed'
                result['failed'] += 1
                stopped = True
        _database_operation(lambda: delivery.save(update_fields=['status', 'accepted_at']))
    if send and stopped:
        recipients = get_user_model().objects.filter(is_active=True).filter(Q(role__in=['it', 'admin']) | Q(is_superuser=True))
        _create_notification('IT warning: login check-in email failed', 'The weekly login check-in run stopped after an SMTP send failed or its acceptance could not be confirmed. Check provider delivery logs before retrying; reserved attempts are not automatically resent. No credentials or recipient details are included in this alert.', recipients)
    return result
