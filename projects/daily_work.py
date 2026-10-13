from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from projects.models import DailyTask, Task
from projects.work_scope import can_update_task


@transaction.atomic
def complete_daily_work(item, user):
    locked_item = get_object_or_404(DailyTask.objects.select_for_update(), pk=item.pk, user=user)
    locked_item.is_done = True
    locked_item.completed_at = timezone.now()
    locked_item.save(update_fields=['is_done', 'completed_at'])
    if locked_item.task_id:
        task = Task.objects.select_for_update().get(pk=locked_item.task_id)
        if can_update_task(user, task):
            task.status = 'done'
            task.save(update_fields=['status', 'progress'])
    return locked_item


@transaction.atomic
def reopen_daily_work(item, user):
    locked_item = get_object_or_404(DailyTask.objects.select_for_update(), pk=item.pk, user=user)
    locked_item.is_done = False
    locked_item.completed_at = None
    locked_item.save(update_fields=['is_done', 'completed_at'])
    if locked_item.task_id:
        task = Task.objects.select_for_update().get(pk=locked_item.task_id)
        if can_update_task(user, task):
            task.status = 'in_progress'
            task.save(update_fields=['status', 'progress'])
    return locked_item
