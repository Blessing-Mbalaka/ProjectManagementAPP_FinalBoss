from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0010_project_import_identity'),
        ('manager', '0008_changelog'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='project',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='book_publication', to='projects.project'),
        ),
        migrations.AddField(
            model_name='paper',
            name='project',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paper_publication', to='projects.project'),
        ),
        migrations.AddField(
            model_name='conference',
            name='project',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conference_publication', to='projects.project'),
        ),
    ]
