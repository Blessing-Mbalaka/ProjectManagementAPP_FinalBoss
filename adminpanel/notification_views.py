"""API views for notification management"""
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from adminpanel.models import Notification
from adminpanel.notification_service import mark_read, unread_count_for, visible_notifications_for


@login_required
@require_http_methods(["GET"])
def get_user_notifications(request):
    """Get recent notifications for the logged-in user"""
    notifications = list(visible_notifications_for(request.user)[:20])
    read_ids = set(
        request.user.notification_receipts.filter(
            notification_id__in=[item.id for item in notifications],
            read_at__isnull=False,
        ).values_list('notification_id', flat=True)
    )
    
    return JsonResponse({
        'success': True,
        'notifications': [
            {
                'id': notif.id,
                'title': notif.title,
                'body': notif.body,
                'priority': notif.priority,
                'created_at': notif.created_at.isoformat(),
                'is_pinned': notif.is_pinned,
                'is_read': notif.id in read_ids,
            }
            for notif in notifications
        ],
        'unread_count': unread_count_for(request.user),
    })


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a notification as read (optional implementation)"""
    notification = get_object_or_404(Notification, id=notification_id)
    mark_read(request.user, notification)
    return JsonResponse({
        'success': True,
        'message': 'Notification marked as read',
        'unread_count': unread_count_for(request.user),
    })
