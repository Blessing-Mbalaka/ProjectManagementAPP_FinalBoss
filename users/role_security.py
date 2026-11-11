"""Server-side privilege change events, independent of browser JavaScript."""
from contextvars import ContextVar
from django.db.models.signals import pre_save, post_save, m2m_changed
from django.dispatch import receiver
from .models import CustomUser

actor_context = ContextVar('privilege_change_actor', default=None)
SECURITY_FIELDS = ('role', 'is_superuser', 'is_staff')


def record_change(user, before, after, event_type='role_change', description=None):
    from adminpanel.models import SecurityEvent
    from adminpanel.security_service import notify_security_event
    context = actor_context.get() or {'username': 'System or management command', 'user_id': None, 'path': ''}
    labels = dict(CustomUser.ROLE_CHOICES)
    old_role, new_role = before.get('role'), after.get('role')
    if description is None:
        if old_role != new_role:
            description = f"{context['username']} changed {user.username}'s role from {labels.get(old_role, old_role)} to {labels.get(new_role, new_role)}."
        else:
            description = f"{context['username']} changed {user.username}'s account privileges."
    event = SecurityEvent.objects.create(
        user=user, event_type=event_type, severity='high', status='open', is_suspicious=True,
        reason=description[:255], path=context.get('path', '')[:500],
        details={'actor': context['username'], 'actor_id': context.get('user_id'), 'target': user.username, 'before': before, 'after': after},
    )
    notify_security_event(event)
    return event


@receiver(pre_save, sender=CustomUser)
def capture_privileges(sender, instance, update_fields=None, using='default', **kwargs):
    instance._before_security_fields = None
    if instance.pk and (update_fields is None or set(update_fields) & set(SECURITY_FIELDS)):
        instance._before_security_fields = sender.objects.using(using).filter(pk=instance.pk).values(*SECURITY_FIELDS).first()


@receiver(post_save, sender=CustomUser)
def audit_privileges(sender, instance, created, update_fields=None, **kwargs):
    before = getattr(instance, '_before_security_fields', None)
    if created or before is None:
        return
    after = {key: getattr(instance, key) if update_fields is None or key in update_fields else value for key, value in before.items()}
    if before != after:
        record_change(instance, before, after)


@receiver(m2m_changed, sender=CustomUser.groups.through)
def audit_role_groups(sender, instance, action, reverse, pk_set, **kwargs):
    if reverse:
        if action.startswith('pre_'):
            users = instance.user_set.all() if pk_set is None else CustomUser.objects.filter(pk__in=pk_set)
            instance._before_reverse_groups = {user.pk: (user, list(user.groups.values_list('name', flat=True))) for user in users}
        elif action.startswith('post_'):
            context = actor_context.get() or {'username': 'System or management command'}
            for user, before in getattr(instance, '_before_reverse_groups', {}).values():
                after = list(user.groups.values_list('name', flat=True))
                if set(before) != set(after):
                    record_change(user, {'role': user.role, 'groups': before}, {'role': user.role, 'groups': after},
                                  description=f"{context['username']} changed {user.username}'s role groups from {', '.join(before) or 'none'} to {', '.join(after) or 'none'}.")
        return
    if action.startswith('pre_'):
        instance._before_role_groups = list(instance.groups.values_list('name', flat=True))
    elif action.startswith('post_'):
        before = getattr(instance, '_before_role_groups', [])
        after = list(instance.groups.values_list('name', flat=True))
        if set(before) != set(after):
            context = actor_context.get() or {'username': 'System or management command'}
            record_change(instance, {'role': instance.role, 'groups': before}, {'role': instance.role, 'groups': after},
                          description=f"{context['username']} changed {instance.username}'s role groups from {', '.join(before) or 'none'} to {', '.join(after) or 'none'}.")
