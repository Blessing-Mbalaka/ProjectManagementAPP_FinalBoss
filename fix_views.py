#!/usr/bin/env python3
import os
import re

file_path = 'adminpanel/views.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the section to replace
old_section = '''    category_totals_dict = {}
    monthly_totals_dict = {}
    for exp in all_expenditures:
        category = exp['category']
        category_totals_dict.setdefault(category, 0)
        category_totals_dict[category] += exp['amount']

        month = exp['month']
        monthly_totals_dict.setdefault(month, 0)
        monthly_totals_dict[month] += exp['amount']

    return render(request, 'adminpanel/finance.html', {
        'cost_centres': cost_centres,
        'all_expenditures': all_expenditures,
        'category_totals': category_totals,
        'monthly_totals': monthly_totals,
        'category_choices': Expenditure.EXPENSE_CATEGORY_CHOICES,
        'payments_by_cc': payments_by_cc,
    })'''

new_section = '''    category_totals_dict = {}
    monthly_totals_dict = {}
    for exp in all_expenditures:
        category = exp['category']
        category_totals_dict.setdefault(category, 0)
        category_totals_dict[category] += exp['amount']

        month = exp['month']
        monthly_totals_dict.setdefault(month, 0)
        monthly_totals_dict[month] += exp['amount']

    # Convert to list of dicts for template
    category_totals = [{'category': cat, 'total': total} for cat, total in sorted(category_totals_dict.items())]
    monthly_totals = [{'month': month, 'total': total} for month, total in sorted(monthly_totals_dict.items())]

    return render(request, 'adminpanel/finance.html', {
        'cost_centres': cost_centres,
        'all_expenditures': all_expenditures,
        'category_totals': category_totals,
        'monthly_totals': monthly_totals,
        'category_choices': Expenditure.EXPENSE_CATEGORY_CHOICES,
        'payments_by_cc': payments_by_cc,
    })'''

if old_section in content:
    content = content.replace(old_section, new_section)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('[SUCCESS] Updated views.py with category_totals conversion')
else:
    print('[ERROR] Could not find old section in views.py')
