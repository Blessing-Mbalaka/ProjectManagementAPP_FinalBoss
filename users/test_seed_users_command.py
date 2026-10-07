import csv
import tempfile
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from adminpanel.models import ResearchCentre
from projects.models import TeamMember


User = get_user_model()


class SeedUsersFromCsvCommandTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name="Centre for digital Transformation")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = Path(self.temp_dir.name) / "users.csv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_csv(self, rows):
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "UserName",
                    "SURNAME",
                    "EMAIL ",
                    "Role in App",
                    "Temporary Password",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_dry_run_deduplicates_rows_without_writing_or_emailing(self):
        repeated = {
            "UserName": "Brilliant ",
            "SURNAME": "Mogaladi",
            "EMAIL ": "brilliantm@uj.ac.za",
            "Role in App": "Staff",
            "Temporary Password": "TestPass123!",
        }
        self.write_csv([repeated, repeated])
        output = StringIO()

        call_command(
            "seed_users_from_csv",
            str(self.csv_path),
            research_centre=self.centre.name,
            dry_run=True,
            stdout=output,
        )

        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("Unique valid users: 1", output.getvalue())
        self.assertIn("Duplicate rows skipped: 1", output.getvalue())

    def test_live_run_creates_users_team_members_and_html_onboarding_emails(self):
        self.write_csv(
            [
                {
                    "UserName": "Noluthando ",
                    "SURNAME": "Gamede",
                    "EMAIL ": "noluthandog@uj.ac.za",
                    "Role in App": "Project Manager",
                    "Temporary Password": "TestPass123!",
                },
                {
                    "UserName": "Raksha",
                    "SURNAME": "Singh",
                    "EMAIL ": "singh.raksha@gmail.com",
                    "Role in App": "Admin",
                    "Temporary Password": "Testpass123!",
                },
            ]
        )

        call_command(
            "seed_users_from_csv",
            str(self.csv_path),
            research_centre=self.centre.name,
            send_onboarding=True,
            login_url="https://projectmanagementapp-finalboss.onrender.com/",
            stdout=StringIO(),
        )

        manager = User.objects.get(username="noluthando")
        raksha = User.objects.get(username="raksha")
        self.assertEqual(manager.role, "manager")
        self.assertEqual(raksha.role, "admin")
        self.assertEqual(manager.research_centre, self.centre)
        self.assertTrue(manager.check_password("TestPass123!"))
        self.assertTrue(raksha.check_password("Testpass123!"))
        self.assertTrue(TeamMember.objects.filter(user=manager).exists())
        self.assertFalse(TeamMember.objects.filter(user=raksha).exists())
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            {message.to[0] for message in mail.outbox},
            {"noluthandog@uj.ac.za", "singh.raksha@gmail.com"},
        )
        for message in mail.outbox:
            self.assertIn("Welcome to the PM App", message.subject)
            self.assertTrue(message.alternatives)
            html_body, mime_type = message.alternatives[0]
            self.assertEqual(mime_type, "text/html")
            self.assertIn("Welcome to the PM App", html_body)

    def test_rerun_skips_existing_user_and_does_not_resend_email(self):
        self.write_csv(
            [
                {
                    "UserName": "Raksha",
                    "SURNAME": "Singh",
                    "EMAIL ": "singh.raksha@gmail.com",
                    "Role in App": "Admin",
                    "Temporary Password": "Testpass123!",
                }
            ]
        )
        command_options = {
            "research_centre": self.centre.name,
            "send_onboarding": True,
            "login_url": "https://projectmanagementapp-finalboss.onrender.com/",
        }

        call_command("seed_users_from_csv", str(self.csv_path), stdout=StringIO(), **command_options)
        mail.outbox.clear()
        output = StringIO()
        call_command("seed_users_from_csv", str(self.csv_path), stdout=output, **command_options)

        self.assertEqual(User.objects.filter(username="raksha").count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("Existing users skipped: 1", output.getvalue())

    def test_multiple_csv_files_are_validated_as_one_batch(self):
        self.write_csv(
            [
                {
                    "UserName": "Noluthando",
                    "SURNAME": "Gamede",
                    "EMAIL ": "noluthandog@uj.ac.za",
                    "Role in App": "Project Manager",
                    "Temporary Password": "TestPass123!",
                }
            ]
        )
        additional_path = Path(self.temp_dir.name) / "additional.csv"
        with additional_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "UserName",
                    "SURNAME",
                    "EMAIL ",
                    "Role in App",
                    "Temporary Password",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "UserName": "Raksha",
                    "SURNAME": "Singh",
                    "EMAIL ": "singh.raksha@gmail.com",
                    "Role in App": "Admin",
                    "Temporary Password": "Testpass123!",
                }
            )
        output = StringIO()

        call_command(
            "seed_users_from_csv",
            str(self.csv_path),
            str(additional_path),
            research_centre=self.centre.name,
            dry_run=True,
            stdout=output,
        )

        self.assertIn("Unique valid users: 2", output.getvalue())

    def test_skip_email_excludes_an_intentional_existing_identity_conflict(self):
        User.objects.create_user(
            username="Blessing",
            email="bjmbalaka@gmail.com",
            password="existing-pass",
            role="admin",
        )
        self.write_csv(
            [
                {
                    "UserName": "Blessing",
                    "SURNAME": "Mbalaka",
                    "EMAIL ": "bmbalaka@uj.ac.za",
                    "Role in App": "Staff",
                    "Temporary Password": "TestPass123!",
                }
            ]
        )
        output = StringIO()

        call_command(
            "seed_users_from_csv",
            str(self.csv_path),
            research_centre=self.centre.name,
            skip_email=["bmbalaka@uj.ac.za"],
            dry_run=True,
            stdout=output,
        )

        self.assertIn("Rows intentionally skipped: 1", output.getvalue())
        self.assertIn("Unique valid users: 0", output.getvalue())
