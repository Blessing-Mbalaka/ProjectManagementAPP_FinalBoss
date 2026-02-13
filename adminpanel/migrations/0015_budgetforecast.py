# Generated migration for BudgetForecast model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('adminpanel', '0014_expenditure_date_from_expenditure_date_to_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='BudgetForecast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.CharField(blank=True, help_text='Legacy field - use date_from and date_to instead', max_length=20, null=True)),
                ('date_from', models.DateField(blank=True, help_text='Start date of salary/expenditure period', null=True)),
                ('date_to', models.DateField(blank=True, help_text='End date of salary/expenditure period', null=True)),
                ('name', models.CharField(max_length=100)),
                ('category', models.CharField(choices=[('Salary', 'Salary'), ('Bursaries', 'Bursaries'), ('Invoices', 'Invoices'), ('Fitness', 'Fitness'), ('Equipment', 'Equipment/Office Resources'), ('Travel', 'Travel')], max_length=50)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('is_released', models.BooleanField(default=False, help_text='True when released to Monthly Expenditure Tracker')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cost_centre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='budget_forecasts', to='adminpanel.costcentre')),
            ],
            options={
                'verbose_name': 'Budget Forecast',
                'verbose_name_plural': 'Budget Forecasts',
                'ordering': ['-created_at'],
            },
        ),
    ]
