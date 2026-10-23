import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('adminpanel', '0031_financial_project_contract_details'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PageVisitLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('path', models.CharField(max_length=500)),
                ('view_name', models.CharField(blank=True, max_length=160)),
                ('method', models.CharField(default='GET', max_length=10)),
                ('visited_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='page_visit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-visited_at']},
        ),
        migrations.AddIndex(
            model_name='pagevisitlog',
            index=models.Index(fields=['user', '-visited_at'], name='admin_visit_user_time_idx'),
        ),
        migrations.AddIndex(
            model_name='pagevisitlog',
            index=models.Index(fields=['path', '-visited_at'], name='admin_visit_path_time_idx'),
        ),
    ]
