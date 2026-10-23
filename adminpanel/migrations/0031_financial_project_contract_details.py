from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('adminpanel', '0030_financial_project_company_and_followups'),
    ]

    operations = [
        migrations.AddField(
            model_name='financialproject',
            name='actual_contract_value',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Confirmed awarded value. Kept separate from the pre-award estimate.',
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='financialproject',
            name='contract_award_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
