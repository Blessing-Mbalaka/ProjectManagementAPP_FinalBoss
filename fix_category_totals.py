#!/usr/bin/env python
"""Fix category_totals and monthly_totals data structure in views.py"""

# Read the file
with open('adminpanel/views.py', 'r') as f:
    content = f.read()

# Find and replace the section
old_code = '''    category_totals = {}
    monthly_totals = {}
    for exp in all_expenditures:
        category = exp['category']
        category_totals.setdefault(category, 0)
        category_totals[category] += exp['amount']

        month = exp['month']
        monthly_totals.setdefault(month, 0)
        monthly_totals[month] += exp['amount']

    return render(request, 'adminpanel/finance.html', {
        'cost_centres': cost_centres,
        'all_expenditures': all_expenditures,
        'category_totals': category_totals,
        'monthly_totals': monthly_totals,
        'category_choices': Expenditure.EXPENSE_CATEGORY_CHOICES,
        'payments_by_cc': payments_by_cc,
    })'''

new_code = '''    category_totals_dict = {}
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

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('adminpanel/views.py', 'w') as f:
        f.write(content)
    print('[SUCCESS] Fixed category_totals and monthly_totals data structure')
else:
    print('[ERROR] Could not find the target code section')
