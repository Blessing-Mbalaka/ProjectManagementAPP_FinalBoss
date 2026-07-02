from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction


class Command(BaseCommand):
    help = (
        "Flush all app data while preserving users (including existing password hashes). "
        "Designed for remote database cleanup with strong safety checks."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted/restored without changing data.",
        )
        parser.add_argument(
            "--remote",
            action="store_true",
            help="Required safety flag for remote cleanup.",
        )
        parser.add_argument(
            "--allow-local",
            action="store_true",
            help="Allow execution on local/dev databases (normally blocked).",
        )
        parser.add_argument(
            "--confirm",
            type=str,
            default="",
            help="Type exactly KEEP_USERS to execute destructive operation.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        is_remote = options["remote"]
        allow_local = options["allow_local"]
        confirm = options["confirm"]

        db_settings = settings.DATABASES["default"]
        engine = db_settings.get("ENGINE", "")
        host = db_settings.get("HOST") or ""
        name = db_settings.get("NAME") or ""

        if not is_remote:
            raise CommandError("Blocked: add --remote to run this command.")

        if not allow_local and ("sqlite" in engine or host in {"", "localhost", "127.0.0.1"}):
            raise CommandError(
                "Blocked: local database detected. Use --allow-local only if you truly intend this."
            )

        if not dry_run and confirm != "KEEP_USERS":
            raise CommandError("Blocked: pass --confirm KEEP_USERS to proceed.")

        User = get_user_model()
        user_model_label = User._meta.label_lower

        # Keep all concrete fields so password hashes and auth flags remain unchanged.
        user_fields = [f.name for f in User._meta.concrete_fields]
        user_rows = list(User.objects.values(*user_fields))

        non_user_counts = []
        total_non_user_rows = 0
        for model in apps.get_models():
            if model._meta.label_lower == user_model_label:
                continue
            if not model._meta.managed or model._meta.proxy:
                continue

            count = model._default_manager.count()
            if count:
                non_user_counts.append((model._meta.label, count))
                total_non_user_rows += count

        self.stdout.write("\n=== FLUSH KEEP USERS PREVIEW ===")
        self.stdout.write(f"Database engine: {engine}")
        self.stdout.write(f"Database host: {host or '(empty)'}")
        self.stdout.write(f"Database name: {name or '(empty)'}")
        self.stdout.write(f"Users to preserve: {len(user_rows)}")
        self.stdout.write(f"Non-user rows to delete: {total_non_user_rows}")

        if non_user_counts:
            self.stdout.write("\nRows that would be deleted by model:")
            for label, count in sorted(non_user_counts):
                self.stdout.write(f"- {label}: {count}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry-run complete. No changes made."))
            return

        self.stdout.write(self.style.WARNING("\nExecuting flush while preserving users..."))

        with transaction.atomic():
            call_command("flush", interactive=False, verbosity=0)
            User.objects.bulk_create([User(**row) for row in user_rows])

            # Keep future inserts safe when explicit IDs are restored.
            sequence_sql = connection.ops.sequence_reset_sql(no_style(), [User])
            if sequence_sql:
                with connection.cursor() as cursor:
                    for sql in sequence_sql:
                        cursor.execute(sql)

        self.stdout.write(self.style.SUCCESS("\nSuccess: all non-user data removed."))
        self.stdout.write(self.style.SUCCESS("Users were restored with existing password hashes."))
