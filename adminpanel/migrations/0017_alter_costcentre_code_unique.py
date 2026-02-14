# Add unique constraint to code field after populating data

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0016_costcentre_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='costcentre',
            name='code',
            field=models.CharField(help_text='University-assigned cost centre code', max_length=20, unique=True),
        ),
    ]
