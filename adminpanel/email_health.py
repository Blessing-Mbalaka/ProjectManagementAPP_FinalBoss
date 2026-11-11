"""Persistent, non-email IT warnings about backup email delivery."""
from email.utils import parseaddr

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import BackupSchedule


WARNINGS = {
    'not_configured': 'Backup SMTP is not configured for offsite delivery. Check the email backend, host, sender and authentication settings. Database recovery emails cannot be relied on until a backup is accepted and its attachment is verified in the recipient mailbox.',
    'failed': 'Backup email delivery failed or was blocked by the mail service or network. Check SMTP credentials, provider restrictions and connectivity, then retry a backup. No completed backup was recorded for the failed attempt.',
}


def configuration_problem():
    backend = settings.EMAIL_BACKEND
    if settings.DEBUG and settings.DB_BACKUP_ALLOW_TEST_EMAIL and backend in {
        'django.core.mail.backends.locmem.EmailBackend', 'django.core.mail.backends.filebased.EmailBackend',
    }:
        return False
    if backend in {
        'django.core.mail.backends.locmem.EmailBackend', 'django.core.mail.backends.filebased.EmailBackend',
        'django.core.mail.backends.console.EmailBackend', 'django.core.mail.backends.dummy.EmailBackend',
    }:
        return True
    if backend == 'django.core.mail.backends.smtp.EmailBackend':
        host = str(settings.EMAIL_HOST or '').strip()
        username, password = settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD
        if not host or bool(username) != bool(password) or (host.lower() == 'smtp.gmail.com' and not username):
            return True
        if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
            return True
    try:
        validate_email(parseaddr(str(settings.DEFAULT_FROM_EMAIL or ''))[1])
    except ValidationError:
        return True
    return False


def update_email_status(state):
    # Row locking also prevents separate web/worker processes from spamming the bell.
    from .security_service import _create_notification
    from users.models import CustomUser
    with transaction.atomic():
        schedule, _ = BackupSchedule.objects.get_or_create(key='database')
        schedule = BackupSchedule.objects.select_for_update().get(pk=schedule.pk)
        changed = schedule.email_delivery_state != state
        schedule.email_delivery_state = state
        schedule.email_checked_at = timezone.now()
        schedule.save(update_fields=['email_delivery_state', 'email_checked_at'])
        if changed and state in WARNINGS:
            recipients = CustomUser.objects.filter(is_active=True).filter(Q(role__in=['it', 'admin']) | Q(is_superuser=True))
            _create_notification('IT warning: backup SMTP ' + ('not configured' if state == 'not_configured' else 'delivery failed'), WARNINGS[state], recipients)
    return schedule


def email_health():
    """Inspect configuration without connecting or sending mail during page loads."""
    if configuration_problem():
        schedule = update_email_status('not_configured')
    else:
        schedule, _ = BackupSchedule.objects.get_or_create(key='database')
        if schedule.email_delivery_state == 'not_configured':
            schedule = update_email_status('unverified')
    return {
        'warning': WARNINGS.get(schedule.email_delivery_state, ''),
        'state': schedule.email_delivery_state,
        'checked_at': schedule.email_checked_at,
    }
