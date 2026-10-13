from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from adminpanel.models import ResearchCentre
from projects.importing import ImportSummary, parse_date_value, read_csv_rows, split_usernames
from projects.models import Assignment, Project, TeamMember


HEADERS = {
    'import_key', 'project_name', 'description', 'project_type', 'status', 'due_date',
    'project_manager_username', 'research_centre', 'team_usernames',
}


class Command(BaseCommand):
    help = 'Validate and import ordinary projects from CSV.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        rows = read_csv_rows(options['csv_path'], HEADERS)
        validated = self._validate(rows)
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f'Dry run complete. Valid rows: {len(validated)}. No records written.'))
            return
        summary = ImportSummary()
        for row in validated:
            with transaction.atomic():
                project, created = Project.objects.update_or_create(
                    import_key=row['import_key'],
                    defaults={
                        'name': row['name'],
                        'description': row['description'],
                        'project_type': row['project_type'],
                        'status': row['status'],
                        'due_date': row['due_date'],
                        'assigned_user': row['manager'],
                        'created_by': row['manager'],
                        'research_centre': row['centre'],
                    },
                )
                for user in row['team_users']:
                    member, _ = TeamMember.objects.get_or_create(
                        user=user,
                        defaults={'full_name': user.get_full_name() or user.username, 'role': user.get_role_display()},
                    )
                    Assignment.objects.update_or_create(
                        project=project,
                        team_member=member,
                        defaults={'responsibility': 'Team member'},
                    )
                summary.created += int(created)
                summary.updated += int(not created)
        self.stdout.write(self.style.SUCCESS(f'Created: {summary.created}; Updated: {summary.updated}; Failed: 0'))

    def _validate(self, rows):
        User = get_user_model()
        project_types = {value for value, _ in Project.PROJECT_TYPES}
        statuses = {value for value, _ in Project.STATUS_CHOICES}
        seen = set()
        validated = []
        for number, raw in rows:
            for field in ('import_key', 'project_name', 'project_type', 'status', 'project_manager_username', 'research_centre'):
                if not raw[field]:
                    raise CommandError(f'Row {number}: {field} is required.')
            if raw['import_key'] in seen:
                raise CommandError(f"Row {number}: duplicate import_key '{raw['import_key']}'.")
            seen.add(raw['import_key'])
            if raw['project_type'] not in project_types:
                raise CommandError(f"Row {number}: invalid project_type '{raw['project_type']}'.")
            if raw['status'] not in statuses:
                raise CommandError(f"Row {number}: invalid status '{raw['status']}'.")
            try:
                manager = User.objects.get(username=raw['project_manager_username'])
            except User.DoesNotExist as exc:
                raise CommandError(f"Row {number}: unknown username '{raw['project_manager_username']}'.") from exc
            try:
                centre = ResearchCentre.objects.get(name=raw['research_centre'])
            except ResearchCentre.DoesNotExist as exc:
                raise CommandError(f"Row {number}: unknown research centre '{raw['research_centre']}'.") from exc
            team_users = []
            for username in split_usernames(raw['team_usernames']):
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist as exc:
                    raise CommandError(f"Row {number}: unknown username '{username}'.") from exc
                if user.research_centre_id and user.research_centre_id != centre.id:
                    raise CommandError(f"Row {number}: username '{username}' belongs to another research centre.")
                team_users.append(user)
            validated.append({
                'import_key': raw['import_key'], 'name': raw['project_name'], 'description': raw['description'][:255],
                'project_type': raw['project_type'], 'status': raw['status'],
                'due_date': parse_date_value(raw['due_date'], row_number=number, field='due_date'),
                'manager': manager, 'centre': centre, 'team_users': team_users,
            })
        return validated
