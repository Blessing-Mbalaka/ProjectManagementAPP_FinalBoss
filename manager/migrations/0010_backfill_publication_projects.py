from django.db import migrations


def backfill_publication_projects(apps, schema_editor):
    Project = apps.get_model('projects', 'Project')
    Book = apps.get_model('manager', 'Book')
    Paper = apps.get_model('manager', 'Paper')
    Conference = apps.get_model('manager', 'Conference')

    configurations = (
        (Book, 'book', {'published': 'completed'}),
        (Paper, 'paper', {'draft': 'planning', 'published': 'completed', 'rejected': 'on-hold'}),
        (Conference, 'conference', {'draft': 'planning', 'presented': 'completed', 'rejected': 'on-hold'}),
    )
    for Model, project_type, status_map in configurations:
        for publication in Model.objects.filter(project__isnull=True).iterator():
            creator_id = getattr(publication, 'created_by_id', None)
            project = Project.objects.create(
                import_key=f'publication:{project_type}:{publication.pk}',
                name=publication.title,
                description=(
                    getattr(publication, 'description', None)
                    or getattr(publication, 'abstract', None)
                    or ''
                )[:255],
                project_type=project_type,
                status=status_map.get(publication.status, 'in-progress'),
                due_date=getattr(publication, 'due_date', None) or getattr(publication, 'conference_date', None),
                created_by_id=creator_id,
            )
            Model.objects.filter(pk=publication.pk).update(project_id=project.pk)


class Migration(migrations.Migration):
    dependencies = [
        ('manager', '0009_publication_project_links'),
    ]

    operations = [
        migrations.RunPython(backfill_publication_projects, migrations.RunPython.noop),
    ]
