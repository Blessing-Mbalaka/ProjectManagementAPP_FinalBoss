from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0008_task_comments'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='dailytask',
            name='task',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='daily_work_items',
                to='projects.task',
            ),
        ),
        migrations.AddField(
            model_name='dailytask',
            name='work_date',
            field=models.DateField(db_index=True, default=django.utils.timezone.localdate),
        ),
        migrations.AddField(
            model_name='dailytask',
            name='completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='dailytask',
            constraint=models.UniqueConstraint(
                condition=models.Q(task__isnull=False),
                fields=('user', 'task', 'work_date'),
                name='unique_daily_linked_task_per_user_date',
            ),
        ),
    ]
