from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('manager', '0011_book_co_authors_users_book_external_authors_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='chapter',
            name='assigned_author',
            field=models.ForeignKey(blank=True, help_text='System user responsible for this chapter.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_book_chapters', to=settings.AUTH_USER_MODEL),
        ),
    ]
