from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from projects.daily_work import complete_daily_work, reopen_daily_work
from projects.forms import DailyTaskForm
from projects.models import DailyTask, Project, Task


User = get_user_model()


class DailyWorkTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", role="manager")
        self.staff = User.objects.create_user(username="staff", password="pass", role="staff")
        self.other = User.objects.create_user(username="other", role="staff")
        self.project = Project.objects.create(
            name="Assigned project", created_by=self.owner, assigned_user=self.staff
        )
        self.task = Task.objects.create(
            project=self.project, title="Assigned task", created_by=self.owner, status="todo"
        )
        self.other_task = Task.objects.create(title="Other task", assigned_to=self.other, created_by=self.owner)
        self.today = timezone.localdate()

    def test_form_offers_only_assigned_pool_and_rejects_unassigned_task(self):
        form = DailyTaskForm(user=self.staff, work_date=self.today)
        self.assertEqual(list(form.fields["task"].queryset), [self.task])

        invalid = DailyTaskForm(
            {"task": self.other_task.id, "work_date": self.today.isoformat()},
            user=self.staff,
            work_date=self.today,
        )
        self.assertFalse(invalid.is_valid())

    def test_same_task_cannot_be_added_twice_for_the_same_day(self):
        DailyTask.objects.create(user=self.staff, task=self.task, title=self.task.title, work_date=self.today)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DailyTask.objects.create(user=self.staff, task=self.task, title=self.task.title, work_date=self.today)

    def test_legacy_null_link_remains_valid_and_task_delete_sets_link_null(self):
        legacy = DailyTask.objects.create(user=self.staff, title="Legacy", task=None, work_date=self.today)
        linked = DailyTask.objects.create(
            user=self.staff, task=self.task, title=self.task.title, work_date=self.today + timedelta(days=1)
        )

        self.task.delete()
        linked.refresh_from_db()

        self.assertIsNone(legacy.task_id)
        self.assertIsNone(linked.task_id)

    def test_completion_and_reopen_synchronize_kanban_status(self):
        item = DailyTask.objects.create(user=self.staff, task=self.task, title=self.task.title, work_date=self.today)

        complete_daily_work(item, self.staff)
        item.refresh_from_db()
        self.task.refresh_from_db()
        self.assertTrue(item.is_done)
        self.assertIsNotNone(item.completed_at)
        self.assertEqual((self.task.status, self.task.progress), ("done", 100))

        reopen_daily_work(item, self.staff)
        item.refresh_from_db()
        self.task.refresh_from_db()
        self.assertFalse(item.is_done)
        self.assertIsNone(item.completed_at)
        self.assertEqual((self.task.status, self.task.progress), ("in_progress", 33))

    def test_daily_delete_and_kanban_delete_use_distinct_endpoints(self):
        item = DailyTask.objects.create(user=self.staff, task=self.task, title=self.task.title, work_date=self.today)
        self.client.force_login(self.staff)

        daily_response = self.client.post(reverse("daily_task_delete", args=[item.id]))
        kanban_response = self.client.post(reverse("delete_task", args=[self.task.id]))

        self.assertRedirects(
            daily_response,
            f"{reverse('dashboard')}?date={self.today.isoformat()}",
        )
        self.assertFalse(DailyTask.objects.filter(id=item.id).exists())
        self.assertEqual(kanban_response.status_code, 403)
        self.assertTrue(Task.objects.filter(id=self.task.id).exists())
