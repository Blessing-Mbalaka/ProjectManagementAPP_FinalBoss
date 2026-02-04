"""
Notification service for sending SMTP emails to stakeholders on form updates
"""
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from adminpanel.models import Notification
from users.models import CustomUser
import logging

logger = logging.getLogger(__name__)


def get_email_recipients(obj, changed_by):
    """
    Get all stakeholders who should be notified of changes
    
    Args:
        obj: Paper or Conference instance
        changed_by: User who made the change (to exclude from notifications)
    
    Returns:
        QuerySet of CustomUser instances to notify
    """
    contributors = obj.get_all_contributors()  # Returns a set
    # Convert set to list and filter out the changed_by user
    recipients_set = contributors - {changed_by}
    # Convert back to QuerySet for consistency
    if recipients_set:
        recipients = CustomUser.objects.filter(id__in=[u.id for u in recipients_set])
    else:
        recipients = CustomUser.objects.none()
    return recipients


def send_update_notification_email(content_type, obj, changes, changed_by):
    """
    Send SMTP email notification to stakeholders when record is updated
    
    Args:
        content_type: 'paper' or 'conference'
        obj: Paper or Conference instance
        changes: List of dicts with keys: field_label, old_value, new_value
        changed_by: User who made the change
    """
    try:
        recipients = get_email_recipients(obj, changed_by)
        
        if not recipients.exists():
            logger.info(f"No recipients to notify for {content_type} {obj.id}")
            return
        
        # Prepare email content
        context = {
            'object_type': content_type.capitalize(),
            'object_title': str(obj),
            'object_id': obj.id,
            'changed_by_user': changed_by,
            'changes': changes,
            'changed_at': obj.updated_at if hasattr(obj, 'updated_at') else None,
        }
        
        # Render email template
        if content_type == 'paper':
            html_message = render_to_string('emails/paper_updated.html', context)
        elif content_type == 'conference':
            html_message = render_to_string('emails/conference_updated.html', context)
        else:
            logger.warning(f"Unknown content_type: {content_type}")
            return
        
        # Get plain text version
        plain_message = strip_tags(html_message)
        
        # Send to each recipient
        recipient_emails = list(recipients.values_list('email', flat=True))
        
        if recipient_emails:
            send_mail(
                subject=f"[Updated] {content_type.capitalize()}: {obj}",
                message=plain_message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=recipient_emails,
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Notification sent for {content_type} {obj.id} to {len(recipient_emails)} recipients")
        
        # Create in-app notification record
        notification = Notification.objects.create(
            title=f"{content_type.capitalize()} Updated: {obj}",
            body=f"The {content_type} '{obj}' was updated by {changed_by.get_full_name() or changed_by.username}. {len(changes)} field(s) changed.",
            priority='normal',
            audience='specific',
            created_by=changed_by,
        )
        notification.recipients.set(recipients)
        
        logger.info(f"In-app notification created for {content_type} {obj.id}")
        
    except Exception as e:
        logger.error(f"Error sending notification email for {content_type} {obj.id}: {str(e)}")
        raise


def create_change_summary(changes):
    """
    Create a human-readable summary of changes
    
    Args:
        changes: List of ChangeLog instances
    
    Returns:
        List of dicts with formatted change information
    """
    summary = []
    for change in changes:
        summary.append({
            'field_label': change.field_label,
            'old_value': change.old_value or '(empty)',
            'new_value': change.new_value or '(empty)',
        })
    return summary
