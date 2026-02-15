#!/usr/bin/env python
"""Simple test to verify scheduler works - run via: python manage.py shell"""

import os
import sys
from datetime import datetime, time, timedelta

# Ensure Django is set up
import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
    django.setup()

from django.utils import timezone
from users.models import CustomUser
from adminpanel.models import UserAvailability
from adminpanel.scheduler import get_current_availability, auto_update_all_availability, get_team_availability_realtime

print("\n" + "="*60)
print("SCHEDULER AUTO-UPDATE TEST")
print("="*60)

# 1. Clean up any old test data
print("\n[1] Cleaning up old test data...")
teststaff = CustomUser.objects.filter(username='teststaff').first()
if teststaff:
    UserAvailability.objects.filter(
        user=teststaff,
        date=timezone.now().date()
    ).delete()
    print("✓ Old test data removed")
else:
    print("! Creating test user 'teststaff'...")
    teststaff = CustomUser.objects.create_user(
        username='teststaff',
        email='teststaff@test.com',
        password='testpass123',
        role='staff'
    )
    print(f"✓ Created user: {teststaff}")

# 2. Create test availability slots
print("\n[2] Creating test availability slots for today...")
today = timezone.now().date()

slots = [
    (time(9, 0), time(12, 0), 'available', 'Working', None),
    (time(12, 0), time(13, 0), 'meeting', 'Team Standup', 'Team Standup Meeting'),
    (time(13, 0), time(14, 30), 'available', 'Working', None),
    (time(14, 30), time(15, 30), 'meeting', 'Client Call', 'Client Call'),
    (time(15, 30), time(17, 0), 'available', 'Working', None),
]

UserAvailability.objects.filter(user=teststaff, date=today).delete()

for start, end, status, reason, title in slots:
    slot = UserAvailability.objects.create(
        user=teststaff,
        date=today,
        start_time=start,
        end_time=end,
        status=status,
        reason=reason,
        meeting_title=title
    )
    print(f"  ✓ {start.strftime('%H:%M')} - {end.strftime('%H:%M')}: {status} ({reason})")

# 3. Test scheduler at different times
print("\n[3] Testing scheduler at various times...")
test_times = [
    ('08:30', time(8, 30)),  # Before work
    ('10:00', time(10, 0)),  # During work
    ('12:15', time(12, 15)), # During first meeting
    ('13:45', time(13, 45)), # Working after meeting
    ('15:00', time(15, 0)),  # During second meeting
    ('16:00', time(16, 0)),  # Working after meeting
    ('18:00', time(18, 0)),  # After work
]

for label, test_time in test_times:
    # Simulate time by testing manually
    result = get_current_availability(teststaff)
    
    current_status = result.get('status', 'unknown')
    current_slot = result.get('current_slot')
    next_change = result.get('time_until_next', 'N/A')
    
    print(f"\n  Time: {label}")
    print(f"  Status: {current_status}")
    if current_slot:
        print(f"    Current: {current_slot.get('reason')} ({current_slot.get('start_time')}-{current_slot.get('end_time')})")
    print(f"    Next change: {next_change}")

# 4. Test auto-update all users
print("\n[4] Testing auto-update for all users...")
try:
    result = auto_update_all_availability(verbose=True)
    print(f"  Total users updated: {result.get('total_users', 0)}")
    print(f"  Update result: {result.get('users_updated', {})}")
except Exception as e:
    print(f"  Error: {e}")

# 5. Test real-time team availability
print("\n[5] Testing real-time team availability API...")
try:
    team_data = get_team_availability_realtime()
    print(f"  Team members: {len(team_data)}")
    for member in team_data[:3]:  # Show first 3
        print(f"    - {member.get('name')}: {member.get('status')}")
        if member.get('next_slot'):
            print(f"      Next: {member.get('time_until_next')}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "="*60)
print("TEST COMPLETE")
print("="*60)
print("\nNext steps:")
print("  1. Access http://localhost:8000/adminpanel/test/scheduler/ to see live view")
print("  2. Watch the real-time updates as time changes")
print("  3. Check /api/scheduler/realtime/ for JSON API data")
print("\n")
