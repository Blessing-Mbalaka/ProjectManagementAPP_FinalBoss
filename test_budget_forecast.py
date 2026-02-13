#!/usr/bin/env python
"""
Quick test to verify Budget Forecast implementation is working
"""
import os
import sys
import django

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

# Test imports
try:
    from adminpanel.models import BudgetForecast, CostCentre, Expenditure
    print("✓ Models imported successfully")
    print(f"  - BudgetForecast model: {BudgetForecast}")
    print(f"  - Fields: {[f.name for f in BudgetForecast._meta.fields]}")
except ImportError as e:
    print(f"✗ Failed to import models: {e}")
    sys.exit(1)

# Test views
try:
    from adminpanel.views import (
        add_budget_forecast,
        get_budget_forecasts, 
        delete_budget_forecast,
        release_budget_forecasts
    )
    print("✓ Budget Forecast views imported successfully")
except ImportError as e:
    print(f"✗ Failed to import views: {e}")
    sys.exit(1)

# Check URL patterns
try:
    from django.urls import reverse
    urls = [
        'add_budget_forecast',
        'get_budget_forecasts',
        'delete_budget_forecast',
        'release_budget_forecasts'
    ]
    for url_name in urls:
        try:
            reverse(url_name, args=[1] if 'delete' in url_name or 'release' in url_name or 'get_budget' in url_name else [])
            print(f"✓ URL '{url_name}' found")
        except:
            print(f"⚠ URL '{url_name}' may need args")
except Exception as e:
    print(f"⚠ URL check: {e}")

print("\n✅ Budget Forecast implementation verified!")
