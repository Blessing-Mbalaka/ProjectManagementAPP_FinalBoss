from datetime import timedelta

from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from .models import Notification, NotificationReceipt


def visible_notifications_for(user, period=None, at=None):
    """Return active notifications whose configured audience includes ``user``."""
    at = at or timezone.now()
    queryset = (
        Notification.objects.filter(
            Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=at),
            Q(expires_at__isnull=True) | Q(expires_at__gt=at),
        )
        .filter(
            Q(audience='all')
            | Q(audience='role', audience_role=getattr(user, 'role', None))
            | Q(audience='specific', recipients=user)
        )
        .select_related('created_by')
        .distinct()
    )

    if period == 'today':
        queryset = queryset.filter(created_at__gte=timezone.localtime(at).replace(hour=0, minute=0, second=0, microsecond=0))
    elif period == 'week':
        queryset = queryset.filter(created_at__gte=at - timedelta(days=7))
    elif period == 'month':
        queryset = queryset.filter(created_at__gte=at - timedelta(days=30))

    return queryset.order_by('-is_pinned', '-created_at')


def unread_count_for(user, at=None):
    return visible_notifications_for(user, at=at).exclude(
        receipts__user=user,
        receipts__read_at__isnull=False,
    ).count()


def mark_read(user, notification):
    if not visible_notifications_for(user).filter(pk=notification.pk).exists():
        raise Http404('Notification not found')
    receipt, _ = NotificationReceipt.objects.update_or_create(
        notification=notification,
        user=user,
        defaults={'read_at': timezone.now()},
    )
    return receipt
