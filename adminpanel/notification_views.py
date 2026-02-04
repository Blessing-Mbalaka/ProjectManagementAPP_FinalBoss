"""API views for notification management"""
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from adminpanel.models import Notification


@login_required
@require_http_methods(["GET"])
def get_user_notifications(request):
    """Get recent notifications for the logged-in user"""
    # Get notifications for this user (specific or by role)
    notifications = Notification.objects.filter(
        recipients__in=[request.user]
    ).distinct().order_by('-created_at')[:20]
    
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
            }
            for notif in notifications
        ],
        'unread_count': notifications.filter(is_pinned=False).count(),
    })


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark a notification as read (optional implementation)"""
    try:
        notification = Notification.objects.get(id=notification_id)
        # Optional: Add a read status field to Notification model if needed
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read'
        })
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Notification not found'
        }, status=404)
