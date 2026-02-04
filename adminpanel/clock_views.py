"""Clock In/Out Views"""
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from .models import ClockInRecord

@login_required
def clock_in(request):
    """Record employee clock in"""
    # Check if already clocked in
    current = ClockInRecord.get_current_session(request.user)
    
    if current:
        return JsonResponse({
            'success': False,
            'message': 'Already clocked in',
            'clocked_in': True
        })
    
    # Create new clock in record
    record = ClockInRecord.objects.create(employee=request.user, clock_in_time=timezone.now())
    
    return JsonResponse({
        'success': True,
        'message': 'Clocked in successfully',
        'clocked_in': True,
        'time': timezone.localtime(record.clock_in_time).strftime('%H:%M:%S')
    })

@login_required
def clock_out(request):
    """Record employee clock out"""
    current = ClockInRecord.get_current_session(request.user)
    
    if not current:
        return JsonResponse({
            'success': False,
            'message': 'Not currently clocked in',
            'clocked_in': False
        })
    
    # Record clock out time
    current.clock_out_time = timezone.now()
    current.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Clocked out successfully',
        'clocked_in': False,
        'duration': current.duration_display,
        'time': timezone.localtime(current.clock_out_time).strftime('%H:%M:%S')
    })

@login_required
def get_clock_status(request):
    """Get current clock status for user"""
    current = ClockInRecord.get_current_session(request.user)
    today_hours = ClockInRecord.get_today_total_hours(request.user)
    
    return JsonResponse({
        'clocked_in': current is not None,
        'clock_in_time': timezone.localtime(current.clock_in_time).strftime('%H:%M:%S') if current else None,
        'duration': current.duration_display if current else None,
        'today_hours': today_hours
    })

@login_required
def clock_history(request):
    """View clock in/out history"""
    records = ClockInRecord.objects.filter(employee=request.user)[:50]
    
    history = []
    for record in records:
        history.append({
            'date': timezone.localtime(record.clock_in_time).strftime('%Y-%m-%d'),
            'clock_in': timezone.localtime(record.clock_in_time).strftime('%H:%M:%S'),
            'clock_out': timezone.localtime(record.clock_out_time).strftime('%H:%M:%S') if record.clock_out_time else '--',
            'duration': record.duration_display,
            'notes': record.notes
        })
    
    return JsonResponse({'history': history})