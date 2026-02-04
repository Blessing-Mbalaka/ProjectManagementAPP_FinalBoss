#!/usr/bin/env python
"""Test the user_activity API endpoint"""
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

# Create test client
client = Client()

# Create a test admin user if doesn't exist
try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    user = User.objects.create_superuser('admin', 'admin@example.com', 'admin')

# Login first
client.login(username='admin', password='admin')

# Test different date ranges
print("🔍 TESTING API ENDPOINT: /adminpanel/api/user-activity/")
print("=" * 60)

test_cases = [
    {'date_range': '30', 'label': 'Last 30 Days'},
    {'date_range': '60', 'label': 'Last 60 Days'},
    {'date_range': '90', 'label': 'Last 90 Days'},
    {'date_range': 'all', 'label': 'All Time'},
]

for test in test_cases:
    url = f"/adminpanel/api/user-activity/?date_range={test['date_range']}"
    response = client.get(url)
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ {test['label']} (date_range={test['date_range']})")
        print(f"   Status: {response.status_code}")
        print(f"   Recent records: {len(data.get('recent_records', []))}")
        print(f"   Total hours: {data.get('total_hours', 0):.2f}h")
        print(f"   Avg daily hours: {data.get('avg_daily_hours', 0):.2f}h")
        print(f"   Days present: {data.get('days_present', 0)}")
        
        # Check heatmap data
        heatmap = data.get('heatmap_data', {})
        total_heatmap_hours = sum(sum(day_hours) for day_hours in heatmap.values())
        print(f"   Heatmap total hours: {total_heatmap_hours:.2f}h")
        
        # Show first recent record if exists
        if data.get('recent_records'):
            first = data['recent_records'][0]
            print(f"   First record: {first['date']} | {first['employee']} | {first['duration']}")
    else:
        print(f"\n❌ {test['label']} - Error {response.status_code}")
        if response.status_code == 302:
            print(f"   Response: Redirected (not authenticated)")
        else:
            print(f"   Response: {response.content[:200]}")
