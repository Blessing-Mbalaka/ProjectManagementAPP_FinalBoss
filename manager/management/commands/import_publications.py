from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from adminpanel.models import ResearchCentre
from manager.models import Book, Conference, Paper
from manager.publication_projects import sync_publication_project
from projects.importing import ImportSummary, parse_date_value, read_csv_rows, split_usernames
from projects.models import Assignment, Project, TeamMember


HEADERS = {
    'kind', 'import_key', 'title', 'description', 'status', 'project_manager_username',
    'research_centre', 'team_usernames',
}


class Command(BaseCommand):
    help = 'Validate and import books, papers, and conferences from CSV.'

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
                project = Project.objects.filter(import_key=row['import_key']).first()
                publication = self._publication_for_project(project, row['kind']) if project else None
                created = publication is None
                publication = self._save_publication(publication, row)
                project = sync_publication_project(
                    publication,
                    actor=row['lead_user'] or row['manager'],
                    manager=row['manager'],
                    research_centre=row['centre'],
                )
                if project.import_key != row['import_key']:
                    project.import_key = row['import_key']
                    project.save(update_fields=['import_key'])
                self._save_relations(publication, project, row)
                summary.created += int(created)
                summary.updated += int(not created)
        self.stdout.write(self.style.SUCCESS(f'Created: {summary.created}; Updated: {summary.updated}; Failed: 0'))

    def _validate(self, rows):
        User = get_user_model()
        seen = set()
        validated = []
        models = {'book': Book, 'paper': Paper, 'conference': Conference}
        for number, raw in rows:
            for field in ('kind', 'import_key', 'title', 'status', 'project_manager_username', 'research_centre'):
                if not raw.get(field):
                    raise CommandError(f'Row {number}: {field} is required.')
            kind = raw['kind']
            if kind not in models:
                raise CommandError(f"Row {number}: kind must be book, paper, or conference.")
            if raw['import_key'] in seen:
                raise CommandError(f"Row {number}: duplicate import_key '{raw['import_key']}'.")
            seen.add(raw['import_key'])
            valid_statuses = {value for value, _ in models[kind].STATUS_CHOICES}
            if raw['status'] not in valid_statuses:
                raise CommandError(f"Row {number}: invalid {kind} status '{raw['status']}'.")
            try:
                manager = User.objects.get(username=raw['project_manager_username'])
                centre = ResearchCentre.objects.get(name=raw['research_centre'])
            except (User.DoesNotExist, ResearchCentre.DoesNotExist) as exc:
                raise CommandError(f'Row {number}: project manager or research centre was not found.') from exc

            def users(field):
                result = []
                for username in split_usernames(raw.get(field, '')):
                    try:
                        user = User.objects.get(username=username)
                    except User.DoesNotExist as exc:
                        raise CommandError(f"Row {number}: unknown username '{username}'.") from exc
                    if user.research_centre_id and user.research_centre_id != centre.id:
                        raise CommandError(f"Row {number}: username '{username}' belongs to another research centre.")
                    result.append(user)
                return result

            if manager.research_centre_id and manager.research_centre_id != centre.id:
                raise CommandError(f"Row {number}: project manager belongs to another research centre.")

            lead_users = users('lead_author_username')
            validated.append({
                'row': number, 'kind': kind, 'import_key': raw['import_key'], 'title': raw['title'],
                'description': raw.get('description', ''), 'status': raw['status'],
                'due_date': parse_date_value(raw.get('due_date', ''), row_number=number, field='due_date'),
                'conference_date': parse_date_value(raw.get('conference_date', ''), row_number=number, field='conference_date'),
                'submission_date': parse_date_value(raw.get('submission_date', ''), row_number=number, field='submission_date'),
                'decision_date': parse_date_value(raw.get('decision_date', ''), row_number=number, field='decision_date'),
                'internal_external': raw.get('internal_external') or 'internal',
                'paper_type': raw.get('paper_type') or 'journal', 'version': raw.get('version') or '1.0',
                'abstract': raw.get('abstract', ''), 'conference_name': raw.get('conference_name', ''),
                'location': raw.get('location', ''), 'publisher': raw.get('publisher', ''),
                'total_chapters': int(raw.get('total_chapters') or 1),
                'completed_chapters': int(raw.get('completed_chapters') or 0),
                'lead_author': raw.get('lead_author', ''), 'target_journal': raw.get('target_journal', ''),
                'manager': manager, 'centre': centre, 'lead_user': lead_users[0] if lead_users else None,
                'coauthors': users('co_author_usernames'), 'reviewers': users('reviewer_usernames'),
                'team_users': users('team_usernames'),
            })
        return validated

    def _publication_for_project(self, project, kind):
        if not project:
            return None
        return getattr(project, f'{kind}_publication', None)

    def _save_publication(self, publication, row):
        if row['kind'] == 'book':
            publication = publication or Book()
            publication.description = row['description']
            publication.due_date = row['due_date']
            publication.publisher = row['publisher']
            publication.total_chapters = row['total_chapters']
            publication.completed_chapters = row['completed_chapters']
        elif row['kind'] == 'paper':
            publication = publication or Paper(manuscript='')
            publication.paper_type = row['paper_type']
            publication.internal_external = row['internal_external']
            publication.version = row['version']
            publication.abstract = row['abstract']
            publication.target_journal = row['target_journal']
            publication.submission_date = row['submission_date']
            publication.decision_date = row['decision_date']
            publication.lead_author_user = row['lead_user']
        else:
            publication = publication or Conference()
            publication.internal_external = row['internal_external']
            publication.conference_name = row['conference_name']
            publication.location = row['location']
            publication.abstract = row['abstract']
            publication.submission_date = row['submission_date']
            publication.conference_date = row['conference_date']
            publication.decision_date = row['decision_date']
            publication.lead_author_user = row['lead_user']
        publication.title = row['title']
        publication.status = row['status']
        publication.lead_author = row['lead_author'] or (row['lead_user'].get_full_name() if row['lead_user'] else '')
        publication.created_by = publication.created_by or row['lead_user'] or row['manager']
        publication.save()
        return publication

    def _save_relations(self, publication, project, row):
        if isinstance(publication, (Paper, Conference)):
            publication.co_authors_users.set(row['coauthors'])
            publication.assigned_reviewers.set(row['reviewers'])
        for user in row['team_users']:
            member, _ = TeamMember.objects.get_or_create(
                user=user,
                defaults={'full_name': user.get_full_name() or user.username, 'role': user.get_role_display()},
            )
            Assignment.objects.update_or_create(
                project=project, team_member=member, defaults={'responsibility': 'Publication contributor'}
            )
