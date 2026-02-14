# Make code field required (NOT NULL)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0017_alter_costcentre_code_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='costcentre',
            name='code',
            field=models.CharField(help_text='University-assigned cost centre code', max_length=20, unique=True),
        ),
    ]
