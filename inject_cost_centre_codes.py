#!/usr/bin/env python
"""
Migration and code injection script
This script applies migrations and injects fake cost centre codes
"""
import os
import sys
from decimal import Decimal

# Add project directory to path
sys.path.insert(0, r'c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage')

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')

import django
django.setup()

from django.core.management import call_command
from adminpanel.models import CostCentre

# Apply migrations
print("Applying migrations...")
call_command('migrate', 'adminpanel')
print("✓ Migrations applied")

# Inject fake codes into existing cost centres
print("\nInjecting fake cost centre codes...")
cost_centres = CostCentre.objects.all()
count = 0

for i, cc in enumerate(cost_centres, 1):
    if not cc.code or cc.code.startswith('TEMP'):
        fake_code = f"CC{i:03d}"
        cc.code = fake_code
        cc.save()
        print(f"  {cc.name} → {fake_code}")
        count += 1

if count == 0:
    print("  No cost centres to update (all have codes)")
else:
    print(f"\n✓ Successfully injected {count} fake codes")

print("\n✓ All done! Cost centres now have unique codes.")
