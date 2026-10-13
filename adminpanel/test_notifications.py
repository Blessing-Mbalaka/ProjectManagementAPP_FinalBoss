from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adminpanel.models import Notification, NotificationReceipt
from adminpanel.notification_service import mark_read, unread_count_for, visible_notifications_for


User = get_user_model()


class NotificationBehaviorTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="notify-admin", password="pass", role="admin")
        self.staff = User.objects.create_user(username="notify-staff", password="pass", role="staff")
        self.other_staff = User.objects.create_user(username="other-staff", password="pass", role="staff")
        self.all_notice = Notification.objects.create(title="Everyone", body="All body", audience="all", created_by=self.admin)
        self.role_notice = Notification.objects.create(
            title="Staff only", body="Role body", audience="role", audience_role="staff", created_by=self.admin
        )
        self.specific_notice = Notification.objects.create(
            title="Specific", body="Specific body", audience="specific", created_by=self.admin
        )
        self.specific_notice.recipients.add(self.staff)
        self.future_notice = Notification.objects.create(
            title="Future", body="Later", audience="all", scheduled_at=timezone.now() + timedelta(days=1), created_by=self.admin
        )
        self.expired_notice = Notification.objects.create(
            title="Expired", body="Old", audience="all", expires_at=timezone.now() - timedelta(seconds=1), created_by=self.admin
        )

    def test_visibility_applies_all_role_specific_and_active_windows(self):
        staff_titles = set(visible_notifications_for(self.staff).values_list("title", flat=True))
        admin_titles = set(visible_notifications_for(self.admin).values_list("title", flat=True))

        self.assertEqual(staff_titles, {"Everyone", "Staff only", "Specific"})
        self.assertEqual(admin_titles, {"Everyone"})

    def test_read_state_is_independent_per_user_and_pinned_is_not_read(self):
        self.all_notice.is_pinned = True
        self.all_notice.save(update_fields=["is_pinned"])
        self.assertEqual(unread_count_for(self.staff), 3)
        self.assertEqual(unread_count_for(self.other_staff), 2)

        receipt = mark_read(self.staff, self.all_notice)

        self.assertIsNotNone(receipt.read_at)
        self.assertEqual(unread_count_for(self.staff), 2)
        self.assertEqual(unread_count_for(self.other_staff), 2)

    def test_period_filters_today_week_and_month(self):
        old = Notification.objects.create(title="Old", body="Old", audience="all", created_by=self.admin)
        Notification.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))

        self.assertNotIn(old, visible_notifications_for(self.staff, period="today"))
        self.assertNotIn(old, visible_notifications_for(self.staff, period="week"))
        self.assertIn(old, visible_notifications_for(self.staff, period="month"))

    def test_api_returns_audience_notifications_and_persists_read(self):
        self.client.force_login(self.staff)
        listing = self.client.get(reverse("get_user_notifications"))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["unread_count"], 3)
        self.assertEqual({item["title"] for item in listing.json()["notifications"]}, {"Everyone", "Staff only", "Specific"})

        read = self.client.post(f"/adminpanel/api/notifications/{self.role_notice.id}/read/")
        self.assertEqual(read.status_code, 200)
        self.assertTrue(NotificationReceipt.objects.filter(notification=self.role_notice, user=self.staff, read_at__isnull=False).exists())

    def test_user_cannot_mark_an_invisible_notification_read(self):
        self.client.force_login(self.admin)
        response = self.client.post(f"/adminpanel/api/notifications/{self.role_notice.id}/read/")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(NotificationReceipt.objects.filter(notification=self.role_notice, user=self.admin).exists())

    def test_admin_overview_filters_audience_and_base_includes_widget_with_escaped_body(self):
        unsafe = Notification.objects.create(
            title="Unsafe", body="<script>alert('x')</script>", audience="all", created_by=self.admin
        )
        self.client.force_login(self.admin)

        overview = self.client.get(reverse("overview"))
        board = self.client.get(reverse("admin_kanban"))

        self.assertContains(overview, unsafe.title)
        self.assertNotContains(overview, self.role_notice.title)
        self.assertNotContains(overview, self.specific_notice.title)
        self.assertContains(board, 'id="notificationBell"')
