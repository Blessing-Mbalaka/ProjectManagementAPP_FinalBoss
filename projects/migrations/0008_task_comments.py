from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('projects', '0007_project_research_centre'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='comments',
            field=models.TextField(blank=True),
        ),
    ]
