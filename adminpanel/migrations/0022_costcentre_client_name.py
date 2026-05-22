from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0021_expenditure_expense_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='costcentre',
            name='client_name',
            field=models.CharField(blank=True, help_text='Client or stakeholder name linked to this cost centre', max_length=150),
        ),
    ]
