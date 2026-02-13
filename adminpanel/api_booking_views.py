"""API views for staff booking and availability management"""
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
import json

from adminpanel.models import UserAvailability, UserLeaveRequest
from users.models import CustomUser
from projects.models import Task, ChatMessage


@login_required
@require_http_methods(["GET"])
def get_team_availability(request, date):
    """Get availability for all team members on a specific date"""
    try:
        # Parse date
        availability_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get all active users except current user
        team_members = CustomUser.objects.filter(
            is_active=True
        ).exclude(
            id=request.user.id
        ).order_by('first_name', 'last_name')
        
        team_data = []
        for user in team_members:
            try:
                availability = UserAvailability.objects.filter(
                    user=user,
                    date=availability_date
                ).first()
                
                status = 'available'
                time_range = ''
                details = ''
                
                if availability:
                    status = availability.status
                    # Add null checks for start_time and end_time
                    if availability.start_time and availability.end_time:
                        time_range = f"{availability.start_time.strftime('%H:%M')} - {availability.end_time.strftime('%H:%M')}"
                    details = availability.reason or availability.meeting_title or ''
                
                # Get user's projects with error handling
                try:
                    projects = list(Task.objects.filter(
                        assigned_to=user
                    ).values_list('project__name', flat=True).distinct())
                except Exception:
                    projects = []
                
                # Safe role extraction
                role = getattr(user, 'role', 'staff')
                
                # Safe initials extraction
                full_name = user.get_full_name() or user.username
                name_parts = full_name.split() if full_name else []
                initials = ''.join([part[0].upper() for part in name_parts if part])
                
                team_data.append({
                    'id': user.id,
                    'name': full_name,
                    'role': role,
                    'status': status,
                    'time_range': time_range,
                    'details': details,
                    'projects': projects,
                    'initials': initials,
                })
            except Exception as user_error:
                # Log but skip problematic users instead of failing entire request
                print(f"Error processing user {user.id}: {str(user_error)}")
                continue
        
        return JsonResponse({
            'success': True,
            'date': date,
            'team_members': team_data,
            'count': len(team_data)
        })
    
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid date format. Use YYYY-MM-DD'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def update_availability(request):
    """Create or update user availability"""
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        date_str = data.get('date')
        status = data.get('status')
        
        if not date_str or not status:
            return JsonResponse({
                'success': False,
                'message': 'Date and status are required'
            }, status=400)
        
        # Parse date
        availability_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Validate status
        valid_statuses = ['available', 'unavailable', 'meeting', 'leave', 'off-hours']
        if status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            }, status=400)
        
        # Parse times with defaults
        start_time = data.get('start_time', '09:00')
        end_time = data.get('end_time', '17:00')
        
        try:
            start_time_obj = datetime.strptime(start_time, '%H:%M').time()
            end_time_obj = datetime.strptime(end_time, '%H:%M').time()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid time format. Use HH:MM'
            }, status=400)
        
        # Check for conflicts if status is 'meeting'
        if status == 'meeting':
            conflict = UserAvailability.check_conflict(
                request.user,
                availability_date,
                start_time_obj,
                end_time_obj
            )
            if conflict:
                return JsonResponse({
                    'success': True,
                    'warning': 'Scheduling conflict detected. You have overlapping meeting on this date.',
                    'conflict': True
                }, status=200)
        
        # Create or update availability
        availability, created = UserAvailability.objects.update_or_create(
            user=request.user,
            date=availability_date,
            defaults={
                'status': status,
                'start_time': start_time_obj,
                'end_time': end_time_obj,
                'meeting_title': data.get('meeting_title', ''),
                'reason': data.get('reason', ''),
                'is_personal': data.get('is_personal', False),
                'created_by': request.user,
            }
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Availability {"created" if created else "updated"} successfully',
            'availability': {
                'id': availability.id,
                'date': availability.date.isoformat(),
                'status': availability.status,
                'start_time': availability.start_time.isoformat(),
                'end_time': availability.end_time.isoformat(),
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_user_availability(request, user_id, date):
    """Get specific user's availability for a date"""
    try:
        user = get_object_or_404(CustomUser, id=user_id, is_active=True)
        availability_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        availability = UserAvailability.objects.filter(
            user=user,
            date=availability_date
        ).first()
        
        if not availability:
            return JsonResponse({
                'success': True,
                'availability': None,
                'status': 'available'
            })
        
        return JsonResponse({
            'success': True,
            'availability': {
                'id': availability.id,
                'user_id': availability.user.id,
                'user_name': availability.user.get_full_name() or availability.user.username,
                'date': availability.date.isoformat(),
                'status': availability.status,
                'start_time': availability.start_time.isoformat(),
                'end_time': availability.end_time.isoformat(),
                'reason': availability.reason,
                'meeting_title': availability.meeting_title,
                'is_personal': availability.is_personal,
            }
        })
    
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid date format'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def request_leave(request):
    """Create a leave request"""
    try:
        data = json.loads(request.body)
        
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        reason = data.get('reason', '')
        
        if not start_date_str or not end_date_str:
            return JsonResponse({
                'success': False,
                'message': 'Start and end dates are required'
            }, status=400)
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
        
        if start_date > end_date:
            return JsonResponse({
                'success': False,
                'message': 'End date must be after start date'
            }, status=400)
        
        # Create leave request
        leave_request = UserLeaveRequest.objects.create(
            user=request.user,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status='pending'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Leave request submitted for approval',
            'leave_request': {
                'id': leave_request.id,
                'start_date': leave_request.start_date.isoformat(),
                'end_date': leave_request.end_date.isoformat(),
                'status': leave_request.status,
            }
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_month_events(request, year, month):
    """Get all availability events for a month (for calendar view)"""
    try:
        year = int(year)
        month = int(month)
        
        if month < 1 or month > 12:
            return JsonResponse({
                'success': False,
                'message': 'Invalid month'
            }, status=400)
        
        # Get first and last day of month
        if month == 12:
            end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        start_date = datetime(year, month, 1).date()
        
        # Get all events for the month
        availabilities = UserAvailability.objects.filter(
            user=request.user,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        events = {}
        for avail in availabilities:
            date_str = avail.date.isoformat()
            if date_str not in events:
                events[date_str] = []
            
            events[date_str].append({
                'type': avail.status,
                'title': avail.meeting_title or avail.reason or avail.status.replace('_', ' ').title(),
                'time': f"{avail.start_time.strftime('%I:%M %p')} - {avail.end_time.strftime('%I:%M %p')}",
                'id': avail.id,
            })
        
        return JsonResponse({
            'success': True,
            'year': year,
            'month': month,
            'events': events
        })
    
    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'message': 'Invalid year or month'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_availability(request, availability_id):
    """Delete an availability record"""
    try:
        availability = get_object_or_404(
            UserAvailability,
            id=availability_id,
            user=request.user
        )
        
        availability.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Availability deleted successfully'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


# ============== STAFF MESSAGING API ENDPOINTS ==============

@login_required
@require_http_methods(["GET"])
def get_staff_inbox(request):
    """Get all message conversations for current user"""
    try:
        # Get all messages where user is sender or recipient
        messages = ChatMessage.objects.filter(
            Q(sender=request.user) | Q(recipient=request.user)
        ).filter(
            submission__isnull=True  # Staff messages only (no submission link)
        ).order_by('-timestamp')
        
        # Build conversation threads
        conversations = {}
        for msg in messages:
            # Determine other party in conversation
            other_user = msg.recipient if msg.sender == request.user else msg.sender
            
            if other_user.id not in conversations:
                conversations[other_user.id] = {
                    'user_id': other_user.id,
                    'name': other_user.get_full_name() or other_user.username,
                    'role': other_user.role if hasattr(other_user, 'role') else 'staff',
                    'last_message': msg.message[:50],
                    'last_message_time': msg.timestamp.isoformat(),
                    'unread_count': 0,
                }
            
            # Count unread messages (sent to current user, not read)
            if msg.recipient == request.user and msg.sender == other_user:
                conversations[other_user.id]['unread_count'] += 1
        
        return JsonResponse({
            'success': True,
            'conversations': list(conversations.values()),
            'total_unread': sum(c['unread_count'] for c in conversations.values())
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_message_thread(request, recipient_id):
    """Get complete message thread with specific user"""
    try:
        recipient = get_object_or_404(CustomUser, id=recipient_id, is_active=True)
        
        # Get all messages between these two users (no submission)
        messages = ChatMessage.objects.filter(
            Q(sender=request.user, recipient=recipient) |
            Q(sender=recipient, recipient=request.user),
            submission__isnull=True
        ).order_by('timestamp')
        
        thread = []
        for msg in messages:
            thread.append({
                'id': msg.id,
                'sender_id': msg.sender.id,
                'sender_name': msg.sender.get_full_name() or msg.sender.username,
                'is_from_current_user': msg.sender == request.user,
                'message': msg.message,
                'timestamp': msg.timestamp.isoformat(),
                'timestamp_display': msg.timestamp.strftime('%H:%M'),
            })
        
        return JsonResponse({
            'success': True,
            'recipient': {
                'id': recipient.id,
                'name': recipient.get_full_name() or recipient.username,
                'role': recipient.role if hasattr(recipient, 'role') else 'staff',
            },
            'messages': thread,
            'total_count': len(thread)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def send_staff_message(request):
    """Send message to another staff member"""
    try:
        data = json.loads(request.body)
        
        recipient_id = data.get('recipient_id')
        message_text = data.get('message', '').strip()
        
        if not recipient_id or not message_text:
            return JsonResponse({
                'success': False,
                'message': 'Recipient and message text are required'
            }, status=400)
        
        # Get recipient
        recipient = get_object_or_404(CustomUser, id=recipient_id, is_active=True)
        
        # Permission check: sender and recipient should be staff/admin
        allowed_roles = ['staff', 'manager', 'admin', 'financialadmin']
        if request.user.role not in allowed_roles or recipient.role not in allowed_roles:
            return JsonResponse({
                'success': False,
                'message': 'Only staff members can send messages to each other'
            }, status=403)
        
        # Create message (submission will be null for staff messages)
        message = ChatMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            message=message_text,
            submission=None  # Staff messages don't link to submissions
        )
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'timestamp': message.timestamp.isoformat(),
            'message': 'Message sent successfully'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_recipients_list(request):
    """Get list of staff members available for messaging"""
    try:
        # Get all active staff/admin users except current user
        allowed_roles = ['staff', 'manager', 'admin', 'financialadmin']
        recipients = CustomUser.objects.filter(
            is_active=True,
            role__in=allowed_roles
        ).exclude(
            id=request.user.id
        ).values(
            'id', 'first_name', 'last_name', 'username', 'role'
        ).order_by('first_name', 'last_name')
        
        # Format response
        recipients_list = []
        for user in recipients:
            full_name = f"{user['first_name']} {user['last_name']}".strip() or user['username']
            recipients_list.append({
                'id': user['id'],
                'name': full_name,
                'username': user['username'],
                'role': user['role'],
                'initials': ''.join([n[0].upper() for n in full_name.split()])
            })
        
        return JsonResponse({
            'success': True,
            'recipients': recipients_list,
            'total_count': len(recipients_list)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_unread_message_count(request):
    """Get count of unread messages for current user"""
    try:
        unread_count = ChatMessage.objects.filter(
            recipient=request.user,
            submission__isnull=True
        ).count()
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)
