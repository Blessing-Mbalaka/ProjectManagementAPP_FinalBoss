"""Encrypt existing payroll and redact historical finance audit values."""
from django.db import migrations


def protect_existing(apps, schema_editor):
    from adminpanel.salary_crypto import encrypt_fields, PROTECTED_FIELDS
    for name in ['Expenditure', 'BudgetForecast']:
        model = apps.get_model('adminpanel', name)
        fields = {field.name for field in model._meta.fields}
        for row in model.objects.filter(category='Salary', salary_ciphertext='').iterator():
            values = {field: getattr(row, field) for field in PROTECTED_FIELDS if field in fields}
            update = {'salary_ciphertext': encrypt_fields(values)}
            for field in values:
                update[field] = 'Protected salary record' if field == 'name' else (None if field == 'oracle_balance' else 0)
            model.objects.filter(pk=row.pk).update(**update)
    audit = apps.get_model('adminpanel', 'AuditLog')
    for row in audit.objects.filter(entity_type='Expenditure').iterator():
        previous = row.previous_values if isinstance(row.previous_values, dict) else {}
        current = row.new_values if isinstance(row.new_values, dict) else {}
        if '(Salary)' in row.entity_name or previous.get('category') == 'Salary' or current.get('category') == 'Salary':
            hidden = {'amount', 'name', 'opening_balance', 'closing_balance', 'oracle_balance'}
            audit.objects.filter(pk=row.pk).update(
                entity_name='Protected salary record',
                previous_values={key: '[protected]' if key in hidden else value for key, value in previous.items()},
                new_values={key: '[protected]' if key in hidden else value for key, value in current.items()},
            )


class Migration(migrations.Migration):
    dependencies = [('adminpanel', '0037_budgetforecast_salary_ciphertext_and_more')]
    operations = [migrations.RunPython(protect_existing)]
