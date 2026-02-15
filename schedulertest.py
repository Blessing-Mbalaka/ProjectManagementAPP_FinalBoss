"""
Test script for the Availability Auto-Scheduler
Tests the scheduler functionality with sample data
"""

import os
import sys
import django
from datetime import datetime, time, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')

try:
    django.setup()
except Exception as e:
    print(f"Django setup error (may be normal if already loaded): {e}")

from django.utils import timezone
from django.test.utils import override_settings
from users.models import CustomUser
from adminpanel.models import UserAvailability
from adminpanel.scheduler import get_current_availability, auto_update_all_availability, get_team_availability_realtime


def cleanup_test_data():
    """Remove test slots to start fresh"""
    UserAvailability.objects.filter(
        user__username='teststaff',
        date=timezone.now().date()
    ).delete()
    print("[TEST] Cleaned up test data\n")


def create_test_slots():
    """Create test availability slots for today"""
    today = timezone.now().date()
    
    try:
        user = CustomUser.objects.get(username='teststaff')
    except CustomUser.DoesNotExist:
        print("[TEST] ERROR: User 'teststaff' not found. Create a staff user with username 'teststaff' first")
        return False
    
    # Create test slots
    slots = [
        {
            'start_time': time(9, 0),
            'end_time': time(12, 0),
            'status': 'available',
            'reason': 'Morning work time',
        },
        {
            'start_time': time(12, 0),
            'end_time': time(13, 0),
            'status': 'meeting',
            'meeting_title': 'Team Standup',
            'reason': 'Daily team meeting',
        },
        {
            'start_time': time(13, 0),
            'end_time': time(14, 30),
            'status': 'available',
            'reason': 'Afternoon work time',
        },
        {
            'start_time': time(14, 30),
            'end_time': time(15, 30),
            'status': 'meeting',
            'meeting_title': 'Client Call',
            'reason': 'Important client discussion',
        },
        {
            'start_time': time(15, 30),
            'end_time': time(17, 0),
            'status': 'available',
            'reason': 'End of day work',
        },
    ]
    
    # Clean up existing slots
    UserAvailability.objects.filter(user=user, date=today).delete()
    
    # Create new slots
    created_slots = []
    for slot_data in slots:
        slot = UserAvailability.objects.create(
            user=user,
            date=today,
            start_time=slot_data['start_time'],
            end_time=slot_data['end_time'],
            status=slot_data['status'],
            reason=slot_data['reason'],
            meeting_title=slot_data.get('meeting_title', ''),
        )
        created_slots.append(slot)
        print(f"[TEST] Created slot: {slot.start_time} - {slot.end_time} ({slot.status})")
    
    print(f"[TEST] Created {len(created_slots)} test slots for {user.username}\n")
    return user


def test_scheduler_at_time(user, test_time_str):
    """Test scheduler at a specific time"""
    print(f"\n{'='*70}")
    print(f"TEST: Checking availability at {test_time_str}")
    print('='*70)
    
    # Parse test time
    try:
        test_time = datetime.strptime(test_time_str, '%H:%M').time()
    except ValueError:
        print(f"[TEST] Invalid time format. Use HH:MM (e.g., 10:30)")
        return
    
    # Simulate time by checking manually
    today = timezone.now().date()
    slots = UserAvailability.objects.filter(user=user, date=today).order_by('start_time')
    
    print(f"\nAll slots for {user.username} today:")
    for slot in slots:
        current = '→ CURRENT' if (slot.start_time <= test_time < slot.end_time) else ''
        print(f"  {slot.start_time} - {slot.end_time}: {slot.status} {current}")
    
    # Manually find current and next slot
    current_slot = None
    next_slot = None
    
    for slot in slots:
        if slot.start_time <= test_time < slot.end_time:
            current_slot = slot
            break
        elif slot.start_time > test_time and next_slot is None:
            next_slot = slot
    
    print(f"\n[RESULT]")
    if current_slot:
        print(f"  Status: {current_slot.status}")
        print(f"  Time: {current_slot.start_time} - {current_slot.end_time}")
        print(f"  Details: {current_slot.reason}")
        if current_slot.meeting_title:
            print(f"  Meeting: {current_slot.meeting_title}")
    else:
        print(f"  Status: available (no scheduled slot)")
    
    if next_slot:
        from datetime import datetime
        delta = datetime.combine(today, next_slot.start_time) - datetime.combine(today, test_time)
        minutes = int(delta.total_seconds() / 60)
        if minutes < 60:
            time_str = f"{minutes} minutes"
        else:
            hours = minutes // 60
            mins = minutes % 60
            time_str = f"{hours}h {mins}m"
        print(f"\n  Next status change: {next_slot.status} in {time_str}")
        print(f"  ({next_slot.start_time}: {next_slot.reason})")
    else:
        print(f"\n  Next status change: None (end of day)")


def run_full_test():
    """Run complete scheduler test"""
    print("\n" + "="*70)
    print("AVAILABILITY AUTO-SCHEDULER TEST")
    print("="*70 + "\n")
    
    # Create test data
    print("[TEST] Setting up test data...")
    user = create_test_slots()
    
    if not user:
        print("[TEST] Failed to create test data")
        return
    
    # Test at different times
    test_times = [
        '08:30',  # Before first slot
        '10:00',  # First slot (available)
        '12:15',  # Middle of standup (meeting)
        '13:45',  # Afternoon available
        '15:00',  # Client call (meeting)
        '16:00',  # Final available slot
        '18:00',  # After all slots
    ]
    
    for test_time in test_times:
        test_scheduler_at_time(user, test_time)
    
    # Test real-time availability (uses actual current time)
    print(f"\n\n{'='*70}")
    print("REAL-TIME AVAILABILITY TEST (Current time)")
    print('='*70)
    print(f"\nChecking {user.username}'s actual current status...")
    availability = get_current_availability(user)
    print(f"\nCurrent Status: {availability['status']}")
    if availability['current_slot']:
        print(f"Current Activity: {availability['current_slot'].reason}")
    if availability['time_until_next']:
        print(f"Next Change: {availability['time_until_next']}")
    
    # Test all users
    print(f"\n\n{'='*70}")
    print("ALL TEAM MEMBERS REAL-TIME AVAILABILITY")
    print('='*70)
    
    team_data = get_team_availability_realtime()
    print(f"\nChecking {len(team_data)} team members...")
    
    for member in team_data:
        status_icon = {
            'available': '🟢',
            'meeting': '🔴',
            'unavailable': '🟡',
            'leave': '⚫',
            'off-hours': '⚪',
        }.get(member['status'], '❓')
        
        print(f"\n{status_icon} {member['name']} ({member['username']}): {member['status']}")
        if member['time_until_next']:
            print(f"   Next change: {member['time_until_next']}")
    
    print(f"\n\n{'='*70}")
    print("TEST COMPLETED")
    print("="*70 + "\n")


if __name__ == '__main__':
    run_full_test()
