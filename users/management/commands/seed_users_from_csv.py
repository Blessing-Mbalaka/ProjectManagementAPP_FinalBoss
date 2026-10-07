import csv
from dataclasses import dataclass, field
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q

from adminpanel.models import ResearchCentre
from projects.models import TeamMember
from users.email_service import send_html_email_safely


ROLE_MAP = {
    "admin": "admin",
    "finance admin": "financialadmin",
    "financial admin": "financialadmin",
    "project manager": "manager",
    "manager": "manager",
    "staff": "staff",
    "centre head": "centrehead",
    "center head": "centrehead",
}


@dataclass(frozen=True)
class UserSeedRow:
    username: str
    first_name: str
    last_name: str
    email: str
    role: str
    password: str
    source_row: int = field(compare=False)


def _normalized_key(value):
    return "_".join((value or "").strip().lower().split())


class Command(BaseCommand):
    help = "Create users from a validated CSV and optionally send onboarding emails."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", nargs="+")
        parser.add_argument("--research-centre", required=True)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--send-onboarding", action="store_true")
        parser.add_argument(
            "--skip-email",
            action="append",
            default=[],
            help="Email address to intentionally exclude; may be supplied more than once.",
        )
        parser.add_argument(
            "--login-url",
            default="https://projectmanagementapp-finalboss.onrender.com/",
        )

    def handle(self, *args, **options):
        csv_paths = [Path(value) for value in options["csv_path"]]
        for csv_path in csv_paths:
            if not csv_path.is_file():
                raise CommandError(f"CSV file not found: {csv_path}")

        try:
            centre = ResearchCentre.objects.get(name=options["research_centre"])
        except ResearchCentre.DoesNotExist as exc:
            raise CommandError(
                f"Research centre not found: {options['research_centre']}"
            ) from exc

        rows, duplicate_count, intentional_skip_count = self._read_and_validate(
            csv_paths,
            skipped_emails=options["skip_email"],
        )
        existing_count = self._validate_database_conflicts(rows)

        self.stdout.write(f"Unique valid users: {len(rows)}")
        self.stdout.write(f"Duplicate rows skipped: {duplicate_count}")
        self.stdout.write(f"Rows intentionally skipped: {intentional_skip_count}")
        self.stdout.write(f"Existing users skipped: {existing_count}")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry run complete. No users or emails were created."))
            return

        created_count = 0
        email_count = 0
        email_failure_count = 0
        User = get_user_model()

        for row in rows:
            if User.objects.filter(
                Q(username__iexact=row.username) | Q(email__iexact=row.email)
            ).exists():
                continue

            with transaction.atomic():
                user = User.objects.create_user(
                    username=row.username,
                    email=row.email,
                    password=row.password,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    role=row.role,
                    research_centre=centre,
                    is_staff=row.role == "admin",
                )
                if row.role in {"manager", "staff"}:
                    TeamMember.objects.get_or_create(
                        user=user,
                        defaults={
                            "full_name": user.get_full_name() or user.username,
                            "role": user.get_role_display(),
                        },
                    )
            created_count += 1

            if options["send_onboarding"]:
                email_sent = self._send_onboarding(
                    user=user,
                    temporary_password=row.password,
                    login_url=options["login_url"],
                )
                if email_sent:
                    email_count += 1
                else:
                    email_failure_count += 1

        self.stdout.write(f"Created users: {created_count}")
        self.stdout.write(f"Onboarding emails accepted: {email_count}")
        self.stdout.write(f"Onboarding emails failed: {email_failure_count}")
        self.stdout.write(self.style.SUCCESS("User seed completed."))

    def _read_and_validate(self, csv_paths, *, skipped_emails):
        valid_rows = []
        duplicate_count = 0
        intentional_skip_count = 0
        skipped_emails = {email.strip().casefold() for email in skipped_emails}
        seen_by_username = {}
        seen_by_email = {}

        for csv_path in csv_paths:
            with csv_path.open("r", newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    raise CommandError(f"CSV has no header row: {csv_path}")

                for row_number, raw_row in enumerate(reader, start=2):
                    row = {_normalized_key(key): (value or "").strip() for key, value in raw_row.items()}
                    first_name = row.get("username", "")
                    username = first_name.lower()
                    last_name = row.get("surname", "")
                    email = row.get("email", "").lower()
                    role_label = row.get("role_in_app", "").casefold()
                    password = row.get("temporary_password", "")

                    if email.casefold() in skipped_emails:
                        intentional_skip_count += 1
                        continue

                    missing = [
                        label
                        for label, value in (
                            ("UserName", username),
                            ("SURNAME", last_name),
                            ("EMAIL", email),
                            ("Role in App", role_label),
                            ("Temporary Password", password),
                        )
                        if not value
                    ]
                    if missing:
                        raise CommandError(
                            f"Row {row_number} is missing required values: {', '.join(missing)}"
                        )
                    try:
                        validate_email(email)
                    except ValidationError as exc:
                        raise CommandError(f"Row {row_number} has invalid email: {email}") from exc

                    role = ROLE_MAP.get(role_label)
                    if not role:
                        raise CommandError(
                            f"Row {row_number} has unsupported role '{row.get('role_in_app', '')}'."
                        )

                    seed_row = UserSeedRow(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        role=role,
                        password=password,
                        source_row=row_number,
                    )
                    existing_username_row = seen_by_username.get(username)
                    existing_email_row = seen_by_email.get(email)
                    if existing_username_row or existing_email_row:
                        previous = existing_username_row or existing_email_row
                        if previous == seed_row:
                            duplicate_count += 1
                            continue
                        raise CommandError(
                            f"Row {row_number} conflicts with row {previous.source_row} "
                            f"for username '{username}' or email '{email}'."
                        )

                    seen_by_username[username] = seed_row
                    seen_by_email[email] = seed_row
                    valid_rows.append(seed_row)

        return valid_rows, duplicate_count, intentional_skip_count

    def _validate_database_conflicts(self, rows):
        User = get_user_model()
        existing_count = 0
        for row in rows:
            matches = list(
                User.objects.filter(
                    Q(username__iexact=row.username) | Q(email__iexact=row.email)
                )[:2]
            )
            if not matches:
                continue
            if len(matches) == 1 and (
                matches[0].username.casefold() == row.username.casefold()
                and matches[0].email.casefold() == row.email.casefold()
            ):
                existing_count += 1
                continue
            raise CommandError(
                f"Database conflict for row {row.source_row}: username '{row.username}' "
                f"or email '{row.email}' belongs to another account."
            )
        return existing_count

    def _send_onboarding(self, *, user, temporary_password, login_url):
        role_name = user.get_role_display()
        text_body = (
            f"Hello {user.first_name or user.username},\n\n"
            "Welcome to the PM App. Your account is ready.\n"
            f"Username: {user.username}\n"
            f"Temporary password: {temporary_password}\n"
            f"Role: {role_name}\n"
            f"Login: {login_url}\n\n"
            "Please change your password after your first login."
        )
        return send_html_email_safely(
            subject="Welcome to the PM App",
            recipient=user.email,
            text_body=text_body,
            html_template="emails/team_onboarding.html",
            context={
                "user": user,
                "temporary_password": temporary_password,
                "role_name": role_name,
                "login_url": login_url,
            },
        )
