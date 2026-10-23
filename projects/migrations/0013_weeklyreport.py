from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0012_project_portfolio_task_import_key_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week_start', models.DateField(db_index=True)),
                ('project_type', models.CharField(choices=[('software', 'Software Project'), ('book', 'Book Project'), ('paper', 'Paper'), ('conference', 'Conference')], max_length=20)),
                ('summary', models.TextField()),
                ('attachment', models.FileField(blank=True, null=True, upload_to='weekly_reports/')),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='weekly_reports', to='projects.project')),
                ('submitted_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='weekly_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-week_start', '-updated_at']},
        ),
        migrations.AddConstraint(
            model_name='weeklyreport',
            constraint=models.UniqueConstraint(fields=('submitted_by', 'project', 'week_start'), name='unique_weekly_report_per_person_project_week'),
        ),
    ]
