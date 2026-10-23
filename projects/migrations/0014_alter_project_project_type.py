from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0013_weeklyreport'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='project_type',
            field=models.CharField(
                choices=[
                    ('software', 'Software Project'),
                    ('book', 'Book Project'),
                    ('paper', 'Paper'),
                    ('conference', 'Conference'),
                    ('financial', 'Financial / Client Bid'),
                ],
                default='software',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='weeklyreport',
            name='project_type',
            field=models.CharField(
                choices=[
                    ('software', 'Software Project'),
                    ('book', 'Book Project'),
                    ('paper', 'Paper'),
                    ('conference', 'Conference'),
                    ('financial', 'Financial / Client Bid'),
                ],
                max_length=20,
            ),
        ),
    ]
