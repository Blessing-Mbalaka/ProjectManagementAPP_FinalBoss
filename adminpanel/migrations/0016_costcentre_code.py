# Generated migration to add code field to CostCentre

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0015_budgetforecast'),
    ]

    operations = [
        migrations.AddField(
            model_name='costcentre',
            name='code',
            field=models.CharField(help_text='University-assigned cost centre code', max_length=20, null=True, blank=True),
        ),
    ]
