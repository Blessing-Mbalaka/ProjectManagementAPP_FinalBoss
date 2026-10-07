from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from adminpanel.models import Notification, ResearchCentre
from projects.models import Assignment, Project, TeamMember


User = get_user_model()


class AssignmentNotificationTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Email Test Centre")
        self.admin = User.objects.create_user(
            username="email-admin",
            password="pass",
            role="admin",
        )
        self.manager = User.objects.create_user(
            username="email-manager",
            email="bjmbalaka@gmail.com",
            password="pass",
            role="manager",
            research_centre=self.centre,
        )
        self.staff = User.objects.create_user(
            username="email-staff",
            email="bjmbalaka@gmail.com",
            password="pass",
            role="staff",
            research_centre=self.centre,
        )
        self.staff_member = TeamMember.objects.create(
            user=self.staff,
            full_name="Email Staff",
            role="Staff",
        )
        self.project = Project.objects.create(
            name="Notification Project",
            description="Assignment notification coverage",
            project_type="software",
            research_centre=self.centre,
            created_by=self.manager,
        )

    def test_team_assignment_notifies_staff_in_app_and_by_html_email(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("assign_team_member", args=[self.project.id]),
            {
                "team_member": self.staff_member.id,
                "responsibility": "Prepare the project report",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Assignment.objects.filter(
                project=self.project,
                team_member=self.staff_member,
            ).exists()
        )
        notification = Notification.objects.get(recipients=self.staff)
        self.assertEqual(notification.audience, "specific")
        self.assertIn(self.project.name, notification.title)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["bjmbalaka@gmail.com"])
        self.assertTrue(mail.outbox[0].alternatives)
        html_body, mime_type = mail.outbox[0].alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn("Prepare the project report", html_body)
        self.assertIn(reverse("staff_kanban"), html_body)

        self.client.force_login(self.staff)
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard_response, notification.title)

    def test_direct_project_assignment_notifies_manager_with_manager_link(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin_assign_project"),
            {
                "project_id": self.project.id,
                "assigned_user": self.manager.id,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.project.refresh_from_db()
        self.assertEqual(self.project.assigned_user, self.manager)
        notification = Notification.objects.get(recipients=self.manager)
        self.assertEqual(notification.audience, "specific")
        self.assertEqual(len(mail.outbox), 1)
        html_body, mime_type = mail.outbox[0].alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn(reverse("manager_kanban"), html_body)

        self.client.force_login(self.manager)
        dashboard_response = self.client.get(reverse("manager_dashboard"))
        self.assertContains(dashboard_response, notification.title)

    @patch(
        "django.core.mail.backends.locmem.EmailBackend.send_messages",
        side_effect=RuntimeError("SMTP unavailable"),
    )
    def test_registration_email_failure_does_not_roll_back_user(self, _send_messages):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("create_user"),
            {
                "username": "fake-email-user",
                "email": "fake-address@example.invalid",
                "role": "staff",
                "research_centre": self.centre.id,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("manage_users"),
            fetch_redirect_response=False,
        )
        self.assertTrue(User.objects.filter(username="fake-email-user").exists())

    def test_registration_email_has_html_version(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("create_user"),
            {
                "username": "html-email-user",
                "email": "bjmbalaka@gmail.com",
                "role": "staff",
                "research_centre": self.centre.id,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(mail.outbox[0].alternatives)
        html_body, mime_type = mail.outbox[0].alternatives[0]
        self.assertEqual(mime_type, "text/html")
        self.assertIn("html-email-user", html_body)
