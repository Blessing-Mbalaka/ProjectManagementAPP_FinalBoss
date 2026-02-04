"""Django signals for manager app - handle notifications on model changes"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
import logging

from manager.models import PaperStatusHistory, PaperComment, Paper, Conference, ChangeLog
from adminpanel.models import Notification
from users.models import CustomUser
from manager.notification_service import send_update_notification_email, create_change_summary

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PaperStatusHistory)
def notify_on_paper_status_change(sender, instance, created, **kwargs):
    """
    When a paper's status changes, notify all contributors
    (lead author, co-authors, creator, assigned reviewers)
    """
    if not created:
        # Only notify on creation of new status history
        return

    paper = instance.paper
    # Get all contributors to notify
    contributors = paper.get_all_contributors()
    
    # Don't notify the person who made the change
    if instance.changed_by:
        contributors.discard(instance.changed_by)

    if not contributors:
        return

    # Create notification
    status_display = dict(paper.STATUS_CHOICES).get(instance.new_status, instance.new_status)
    title = f"Paper Status Updated: {paper.title}"
    body = f"Paper '{paper.title}' status changed to {status_display}"
    
    if instance.reason:
        body += f"\n\nReason: {instance.reason}"

    notification = Notification.objects.create(
        title=title,
        body=body,
        priority='normal',
        audience='specific',
        created_by=instance.changed_by,
    )
    
    # Add all contributors as recipients
    notification.recipients.set(contributors)


@receiver(post_save, sender=PaperComment)
def notify_on_paper_comment(sender, instance, created, **kwargs):
    """
    When a comment is made on a paper, notify all contributors
    (lead author, co-authors, creator, assigned reviewers)
    except the commenter
    """
    if not created:
        # Only notify on creation of new comment
        return

    paper = instance.paper
    # Get all contributors to notify
    contributors = paper.get_all_contributors()
    
    # Don't notify the commenter
    contributors.discard(instance.user)

    if not contributors:
        return

    # Create notification
    title = f"New Comment on Paper: {paper.title}"
    body = f"{instance.user.get_full_name() or instance.user.username} commented on '{paper.title}':\n\n{instance.text[:200]}..."
    
    if len(instance.text) <= 200:
        body = f"{instance.user.get_full_name() or instance.user.username} commented on '{paper.title}':\n\n{instance.text}"

    notification = Notification.objects.create(
        title=title,
        body=body,
        priority='normal',
        audience='specific',
        created_by=instance.user,
    )
    
    # Add all contributors as recipients
    notification.recipients.set(contributors)


@receiver(post_save, sender=Paper)
def sync_paper_reviewer_changes(sender, instance, created, **kwargs):
    """
    (Optional) When paper is saved, ensure assigned_reviewers M2M is in sync with reviewers M2M
    This bridges the new and old relationship patterns
    """
    pass  # Can be used for syncing if needed in future


@receiver(post_save, sender=Conference)
def sync_conference_reviewer_changes(sender, instance, created, **kwargs):
    """
    (Optional) When conference is saved, ensure assigned_reviewers M2M is in sync with reviewers M2M
    This bridges the new and old relationship patterns
    """
    pass  # Can be used for syncing if needed in future


# Store original values before update to detect changes
_paper_original_values = {}
_conference_original_values = {}


@receiver(pre_save, sender=Paper)
def capture_paper_original_values(sender, instance, **kwargs):
    """Capture original field values before update"""
    global _paper_original_values
    
    if instance.pk:  # Only for updates, not new instances
        try:
            original = Paper.objects.get(pk=instance.pk)
            _paper_original_values[instance.pk] = {
                'title': original.title,
                'paper_type': original.paper_type,
                'internal_external': original.internal_external,
                'status': original.status,
                'lead_author_user': original.lead_author_user_id,
                'abstract': original.abstract,
                'submission_date': original.submission_date,
                'decision_date': original.decision_date,
                'feedback_text': original.feedback_text,
            }
        except Paper.DoesNotExist:
            pass


@receiver(post_save, sender=Paper)
def notify_on_paper_form_update(sender, instance, created, **kwargs):
    """
    When a paper is updated via form, log changes and notify stakeholders
    """
    global _paper_original_values
    
    if created:
        # Don't notify on creation, only on updates
        _paper_original_values.pop(instance.pk, None)
        return
    
    # Get user from request context - should be set by the view
    changed_by = getattr(instance, '_changed_by', None)
    if not changed_by:
        return  # No change user set, skip notification
    
    original_values = _paper_original_values.pop(instance.pk, {})
    if not original_values:
        return  # No original values captured
    
    # Detect changes
    changes = []
    field_labels = {
        'title': 'Title',
        'paper_type': 'Paper Type',
        'internal_external': 'Classification',
        'status': 'Status',
        'lead_author_user': 'Lead Author',
        'abstract': 'Abstract',
        'submission_date': 'Submission Date',
        'decision_date': 'Decision Date',
        'feedback_text': 'Feedback',
    }
    
    for field, label in field_labels.items():
        old_val = original_values.get(field)
        
        if field == 'lead_author_user':
            new_val = instance.lead_author_user_id
            if old_val != new_val:
                old_user = CustomUser.objects.filter(id=old_val).first()
                new_user = instance.lead_author_user
                ChangeLog.log_change(
                    'paper', instance, field, label,
                    str(old_user) if old_user else None,
                    str(new_user) if new_user else None,
                    changed_by
                )
                changes.append({
                    'field_label': label,
                    'old_value': str(old_user) if old_user else '(empty)',
                    'new_value': str(new_user) if new_user else '(empty)',
                })
        else:
            new_val = getattr(instance, field)
            if old_val != new_val:
                ChangeLog.log_change(
                    'paper', instance, field, label, old_val, new_val, changed_by
                )
                changes.append({
                    'field_label': label,
                    'old_value': old_val or '(empty)',
                    'new_value': new_val or '(empty)',
                })
    
    # Check M2M changes
    if hasattr(instance, '_co_authors_changed') and instance._co_authors_changed:
        changes.append({
            'field_label': 'Co-Authors',
            'old_value': f"{len(instance._co_authors_changed['old'])} authors",
            'new_value': f"{len(instance._co_authors_changed['new'])} authors",
        })
        ChangeLog.log_change(
            'paper', instance, 'co_authors_users', 'Co-Authors',
            ', '.join(str(u) for u in instance._co_authors_changed['old']),
            ', '.join(str(u) for u in instance._co_authors_changed['new']),
            changed_by
        )
    
    if hasattr(instance, '_reviewers_changed') and instance._reviewers_changed:
        changes.append({
            'field_label': 'Assigned Reviewers',
            'old_value': f"{len(instance._reviewers_changed['old'])} reviewers",
            'new_value': f"{len(instance._reviewers_changed['new'])} reviewers",
        })
        ChangeLog.log_change(
            'paper', instance, 'assigned_reviewers', 'Assigned Reviewers',
            ', '.join(str(u) for u in instance._reviewers_changed['old']),
            ', '.join(str(u) for u in instance._reviewers_changed['new']),
            changed_by
        )
    
    # Send notifications if there were changes
    if changes:
        try:
            send_update_notification_email('paper', instance, changes, changed_by)
        except Exception as e:
            logger.error(f"Failed to send paper update notification: {str(e)}")


@receiver(pre_save, sender=Conference)
def capture_conference_original_values(sender, instance, **kwargs):
    """Capture original field values before update"""
    global _conference_original_values
    
    if instance.pk:  # Only for updates, not new instances
        try:
            original = Conference.objects.get(pk=instance.pk)
            _conference_original_values[instance.pk] = {
                'conference_name': original.conference_name,
                'location': original.location,
                'conference_date': original.conference_date,
                'lead_author_user': original.lead_author_user_id,
            }
        except Conference.DoesNotExist:
            pass


@receiver(post_save, sender=Conference)
def notify_on_conference_form_update(sender, instance, created, **kwargs):
    """
    When a conference is updated via form, log changes and notify stakeholders
    """
    global _conference_original_values
    
    if created:
        # Don't notify on creation, only on updates
        _conference_original_values.pop(instance.pk, None)
        return
    
    # Get user from request context - should be set by the view
    changed_by = getattr(instance, '_changed_by', None)
    if not changed_by:
        return  # No change user set, skip notification
    
    original_values = _conference_original_values.pop(instance.pk, {})
    if not original_values:
        return  # No original values captured
    
    # Detect changes
    changes = []
    field_labels = {
        'conference_name': 'Conference Name',
        'location': 'Location',
        'conference_date': 'Conference Date',
        'lead_author_user': 'Lead Author',
    }
    
    for field, label in field_labels.items():
        old_val = original_values.get(field)
        
        if field == 'lead_author_user':
            new_val = instance.lead_author_user_id
            if old_val != new_val:
                old_user = CustomUser.objects.filter(id=old_val).first()
                new_user = instance.lead_author_user
                ChangeLog.log_change(
                    'conference', instance, field, label,
                    str(old_user) if old_user else None,
                    str(new_user) if new_user else None,
                    changed_by
                )
                changes.append({
                    'field_label': label,
                    'old_value': str(old_user) if old_user else '(empty)',
                    'new_value': str(new_user) if new_user else '(empty)',
                })
        else:
            new_val = getattr(instance, field)
            if old_val != new_val:
                ChangeLog.log_change(
                    'conference', instance, field, label, old_val, new_val, changed_by
                )
                changes.append({
                    'field_label': label,
                    'old_value': old_val or '(empty)',
                    'new_value': new_val or '(empty)',
                })
    
    # Check M2M changes
    if hasattr(instance, '_co_authors_changed') and instance._co_authors_changed:
        changes.append({
            'field_label': 'Co-Authors',
            'old_value': f"{len(instance._co_authors_changed['old'])} authors",
            'new_value': f"{len(instance._co_authors_changed['new'])} authors",
        })
        ChangeLog.log_change(
            'conference', instance, 'co_authors_users', 'Co-Authors',
            ', '.join(str(u) for u in instance._co_authors_changed['old']),
            ', '.join(str(u) for u in instance._co_authors_changed['new']),
            changed_by
        )
    
    if hasattr(instance, '_reviewers_changed') and instance._reviewers_changed:
        changes.append({
            'field_label': 'Assigned Reviewers',
            'old_value': f"{len(instance._reviewers_changed['old'])} reviewers",
            'new_value': f"{len(instance._reviewers_changed['new'])} reviewers",
        })
        ChangeLog.log_change(
            'conference', instance, 'assigned_reviewers', 'Assigned Reviewers',
            ', '.join(str(u) for u in instance._reviewers_changed['old']),
            ', '.join(str(u) for u in instance._reviewers_changed['new']),
            changed_by
        )
    
    # Send notifications if there were changes
    if changes:
        try:
            send_update_notification_email('conference', instance, changes, changed_by)
        except Exception as e:
            logger.error(f"Failed to send conference update notification: {str(e)}")
