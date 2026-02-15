"""
Availability Status Auto-Scheduler
Automatically updates user availability status based on meeting times
"""

from django.utils import timezone
from datetime import datetime, time
from adminpanel.models import UserAvailability
from users.models import CustomUser
import logging

logger = logging.getLogger(__name__)


def get_current_availability(user):
    """
    Get the current availability status for a user based on their schedule
    
    Args:
        user: CustomUser instance
        
    Returns:
        dict: {
            'status': str (available/meeting/unavailable/leave),
            'current_slot': UserAvailability or None,
            'next_slot': UserAvailability or None,
            'time_until_next': str (e.g., "in 15 minutes"),
        }
    """
    now = timezone.now()
    today = now.date()
    current_time = now.time()
    
    print(f"[SCHEDULER] Checking {user.username}: Current time = {current_time}, Date = {today}")
    
    # Get all availability entries for today, ordered by start time
    today_slots = UserAvailability.objects.filter(
        user=user,
        date=today
    ).order_by('start_time')
    
    if not today_slots.exists():
        print(f"[SCHEDULER] No slots found for {user.username} on {today}")
        return {
            'status': 'available',
            'current_slot': None,
            'next_slot': None,
            'time_until_next': None,
        }
    
    current_slot = None
    next_slot = None
    
    # Find current slot (time falls within start_time and end_time)
    for slot in today_slots:
        print(f"[SCHEDULER]   Checking slot: {slot.start_time} - {slot.end_time}, Status: {slot.status}")
        
        # Check if current time is within this slot
        if slot.start_time <= current_time < slot.end_time:
            print(f"[SCHEDULER]   ✓ CURRENT SLOT FOUND: {slot.status}")
            current_slot = slot
            break
        elif slot.start_time > current_time and next_slot is None:
            # First slot that's in the future
            next_slot = slot
    
    # Calculate time until next slot
    time_until_next = None
    if next_slot:
        delta = datetime.combine(today, next_slot.start_time) - datetime.combine(today, current_time)
        minutes = int(delta.total_seconds() / 60)
        if minutes < 60:
            time_until_next = f"in {minutes} minutes"
        else:
            hours = minutes // 60
            mins = minutes % 60
            time_until_next = f"in {hours}h {mins}m"
    
    result = {
        'status': current_slot.status if current_slot else 'available',
        'current_slot': current_slot,
        'next_slot': next_slot,
        'time_until_next': time_until_next,
    }
    
    print(f"[SCHEDULER] Result for {user.username}: Status={result['status']}, Next={time_until_next}")
    return result


def auto_update_all_availability(verbose=False):
    """
    Check all users and auto-update their availability based on current time
    
    Args:
        verbose: bool - print debug info
        
    Returns:
        dict: {
            'total_users': int,
            'users_updated': dict mapping username to status,
            'timestamp': str,
        }
    """
    now = timezone.now()
    
    if verbose:
        print(f"\n[SCHEDULER] Starting auto-update at {now}")
    
    # Get all active staff/admin users
    users = CustomUser.objects.filter(
        is_active=True,
        role__in=['staff', 'manager', 'admin', 'financialadmin']
    )
    
    users_updated = {}
    
    for user in users:
        availability = get_current_availability(user)
        users_updated[user.username] = availability['status']
        
        if verbose:
            msg = f"[SCHEDULER] {user.username}: {availability['status']}"
            if availability['time_until_next']:
                msg += f" (Next change {availability['time_until_next']})"
            print(msg)
    
    if verbose:
        print(f"[SCHEDULER] Completed. Updated {len(users_updated)} users\n")
    
    return {
        'total_users': users.count(),
        'users_updated': users_updated,
        'timestamp': now.isoformat(),
    }


def get_team_availability_realtime(team_members=None, date=None):
    """
    Get real-time availability for team members
    Uses current time to determine actual status
    
    Args:
        team_members: list of CustomUser objects (if None, get all staff)
        date: specific date to check (if None, use today)
        
    Returns:
        list: [
            {
                'user_id': int,
                'username': str,
                'name': str,
                'status': str,
                'current_slot': dict or None,
                'next_slot': dict or None,
                'time_until_next': str or None,
            },
            ...
        ]
    """
    if date is None:
        date = timezone.now().date()
    
    if team_members is None:
        team_members = CustomUser.objects.filter(
            is_active=True,
            role__in=['staff', 'manager', 'admin', 'financialadmin']
        )
    
    team_data = []
    
    for user in team_members:
        availability = get_current_availability(user)
        
        team_data.append({
            'user_id': user.id,
            'username': user.username,
            'name': f"{user.first_name} {user.last_name}".strip() or user.username,
            'status': availability['status'],
            'current_slot': {
                'meeting_title': availability['current_slot'].meeting_title,
                'reason': availability['current_slot'].reason,
                'start_time': availability['current_slot'].start_time.isoformat(),
                'end_time': availability['current_slot'].end_time.isoformat(),
            } if availability['current_slot'] else None,
            'next_slot': {
                'status': availability['next_slot'].status,
                'meeting_title': availability['next_slot'].meeting_title,
                'start_time': availability['next_slot'].start_time.isoformat(),
            } if availability['next_slot'] else None,
            'time_until_next': availability['time_until_next'],
        })
    
    return team_data
