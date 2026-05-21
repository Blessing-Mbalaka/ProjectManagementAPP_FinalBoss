from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0020_alter_expenditure_oracle_balance_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='expenditure',
            name='expense_id',
            field=models.CharField(blank=True, db_index=True, help_text='External/import identifier used to prevent duplicate uploaded expenses', max_length=100, null=True, unique=True),
        ),
    ]
