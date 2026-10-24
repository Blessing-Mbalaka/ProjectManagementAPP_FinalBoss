"""API views for staff booking and availability management"""
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from datetime import datetime, timedelta
import json
import os
import io

from adminpanel.models import UserAvailability, UserLeaveRequest
from users.models import CustomUser
from projects.models import Project, Task, ChatMessage
from projects.scope import scope_projects_for_user
from projects.work_scope import manageable_projects_for
from users.roles import has_role


@login_required
@require_http_methods(["GET"])
def get_team_availability(request, date):
    """Get availability for all team members on a specific date"""
    try:
        # Parse date
        availability_date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Get all active users (including current user so they see themselves in the list)
        team_members = CustomUser.objects.filter(
            is_active=True
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
    """Create or update user availability for a date range"""
    try:
        from datetime import timedelta
        data = json.loads(request.body)
        
        # Validate required fields
        start_date_str = data.get('start_date') or data.get('date')  # Support both formats
        end_date_str = data.get('end_date') or data.get('date')
        status = data.get('status')
        
        if not start_date_str or not end_date_str or not status:
            return JsonResponse({
                'success': False,
                'message': 'Start date, end date, and status are required'
            }, status=400)
        
        # Parse dates
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
        
        # Validate date range
        if start_date > end_date:
            return JsonResponse({
                'success': False,
                'message': 'Start date must be before or equal to end date'
            }, status=400)
        
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
        
        # Create or update availability for each day in range
        current_date = start_date
        created_count = 0
        updated_count = 0
        
        while current_date <= end_date:
            # Check for conflicts if status is 'meeting'
            if status == 'meeting':
                conflict = UserAvailability.check_conflict(
                    request.user,
                    current_date,
                    start_time_obj,
                    end_time_obj
                )
                if conflict:
                    return JsonResponse({
                        'success': True,
                        'warning': f'Scheduling conflict detected on {current_date}. You have overlapping meeting on this date.',
                        'conflict': True
                    }, status=200)
            
            # Create or update availability for this date
            availability, created = UserAvailability.objects.update_or_create(
                user=request.user,
                date=current_date,
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
            
            if created:
                created_count += 1
            else:
                updated_count += 1
            
            # Move to next day
            current_date += timedelta(days=1)
        
        total_days = (end_date - start_date).days + 1
        message = f'Availability updated for {total_days} day{"s" if total_days != 1 else ""}'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'created_count': created_count,
            'updated_count': updated_count,
            'total_days': total_days
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

MESSAGE_ROLES = ('staff', 'manager', 'admin', 'centrehead', 'dean', 'financialadmin', 'supervisor')


def _can_send_staff_messages(user):
    return has_role(user, *MESSAGE_ROLES)


def _message_recipients_for(user):
    return CustomUser.objects.filter(is_active=True, role__in=MESSAGE_ROLES).exclude(pk=user.pk)


def _broadcast_projects_for(user):
    projects = Project.objects.select_related('assigned_user', 'created_by').prefetch_related(
        'assignments__team_member__user', 'tasks__assigned_to'
    )
    if has_role(user, 'admin', 'dean'):
        return projects
    if has_role(user, 'centrehead'):
        return scope_projects_for_user(projects, user)
    if has_role(user, 'manager', 'financialadmin'):
        return manageable_projects_for(user, projects)
    return projects.filter(
        Q(created_by=user)
        | Q(assigned_user=user)
        | Q(assignments__team_member__user=user)
        | Q(tasks__assigned_to=user)
    ).distinct()

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
            msg_data = {
                'id': msg.id,
                'sender_id': msg.sender.id,
                'sender_name': msg.sender.get_full_name() or msg.sender.username,
                'is_from_current_user': msg.sender == request.user,
                'message': msg.message,
                'timestamp': msg.timestamp.isoformat(),
                'timestamp_display': msg.timestamp.strftime('%H:%M'),
            }
            # Add attachment info if exists
            if msg.attachment:
                msg_data['has_attachment'] = True
                msg_data['attachment_url'] = f"/adminpanel/api/messages/attachment/{msg.id}/download/"
                msg_data['attachment_name'] = os.path.basename(msg.attachment.name)
            else:
                msg_data['has_attachment'] = False
            thread.append(msg_data)
        
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


# Supported file formats for uploads
SUPPORTED_FILE_FORMATS = {
    'application/pdf': '.pdf',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.ms-excel': '.xls',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/vnd.ms-powerpoint': '.ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'application/zip': '.zip',
    'application/x-rar-compressed': '.rar',
    'application/x-7z-compressed': '.7z',
}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB

def validate_file_upload(file_obj):
    """Validate uploaded file format and size"""
    print(f"[FILE VALIDATION] Validating: {file_obj.name}, Size: {file_obj.size}, Type: {file_obj.content_type}")
    
    # Check file size
    if file_obj.size > MAX_UPLOAD_SIZE:
        error = f"File too large. Maximum 50MB allowed (current: {file_obj.size / 1024 / 1024:.1f}MB)"
        print(f"[FILE VALIDATION] ERROR: {error}")
        return False, error
    
    # Check file type by MIME type
    if file_obj.content_type in SUPPORTED_FILE_FORMATS:
        print(f"[FILE VALIDATION] File type supported: {file_obj.content_type}")
        return True, None
    
    # Check by file extension as fallback
    file_name = file_obj.name.lower()
    supported_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.rar', '.7z']
    has_valid_extension = any(file_name.endswith(ext) for ext in supported_extensions)
    
    if has_valid_extension:
        print(f"[FILE VALIDATION] File extension supported")
        return True, None
    
    # Unsupported format
    error = "Unsupported file format. Supported types: PDF, Word (.doc, .docx), Excel (.xls, .xlsx), PowerPoint (.ppt, .pptx), Images (.jpg, .png, .gif), Archives (.zip, .rar, .7z)"
    print(f"[FILE VALIDATION] ERROR: {error}")
    return False, error

@login_required
@require_http_methods(["POST"])
def send_staff_message(request):
    """Send message to another staff member (supports optional file attachment)"""
    try:
        # Determine content type
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Handle multipart/form-data (with file upload)
            recipient_id = request.POST.get('recipient_id')
            message_text = request.POST.get('message', '').strip()
            attachment = request.FILES.get('attachment') if 'attachment' in request.FILES else None
        else:
            # Handle JSON (original format)
            data = json.loads(request.body)
            recipient_id = data.get('recipient_id')
            message_text = data.get('message', '').strip()
            attachment = None
        
        if not recipient_id or not message_text:
            return JsonResponse({
                'success': False,
                'message': 'Recipient and message text are required'
            }, status=400)
        
        # Validate attachment if present
        if attachment:
            is_valid, error_msg = validate_file_upload(attachment)
            if not is_valid:
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                }, status=400)
        
        # Get recipient
        recipient = get_object_or_404(CustomUser, id=recipient_id, is_active=True)
        
        # Permission check: sender and recipient should be staff/admin
        if not _can_send_staff_messages(request.user) or recipient.role not in MESSAGE_ROLES:
            return JsonResponse({
                'success': False,
                'message': 'Only staff members can send messages to each other'
            }, status=403)
        
        # Create message (submission will be null for staff messages)
        message = ChatMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            message=message_text,
            submission=None,  # Staff messages don't link to submissions
            attachment=attachment  # Optional attachment (already validated)
        )
        
        print(f"[MESSAGE SENT] ID: {message.id}, From: {request.user.id}, To: {recipient_id}, Has Attachment: {attachment is not None}")
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'timestamp': message.timestamp.isoformat(),
            'has_attachment': attachment is not None,
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
    if not _can_send_staff_messages(request.user):
        return JsonResponse({'success': False, 'message': 'Your account cannot send staff messages.'}, status=403)
    try:
        # Get all active staff/admin users except current user
        recipients = _message_recipients_for(request.user).values(
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
        
        projects_list = [
            {'id': project.id, 'name': project.name, 'project_type': project.get_project_type_display()}
            for project in _broadcast_projects_for(request.user).order_by('name')
        ]

        return JsonResponse({
            'success': True,
            'recipients': recipients_list,
            'projects': projects_list,
            'total_count': len(recipients_list)
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def new_broadcast_message(request):
    """Create one new message for selected people or every active member of a project team."""
    if not _can_send_staff_messages(request.user):
        return JsonResponse({'success': False, 'message': 'Your account cannot send staff broadcasts.'}, status=403)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid broadcast request.'}, status=400)

    message_text = str(data.get('message', '')).strip()
    audience = data.get('audience')
    if not message_text:
        return JsonResponse({'success': False, 'message': 'Please enter a broadcast message.'}, status=400)

    if audience == 'project':
        project_id = data.get('project_id')
        project = _broadcast_projects_for(request.user).filter(pk=project_id).first()
        if not project:
            return JsonResponse(
                {'success': False, 'message': 'That project is outside your permitted project scope.'},
                status=403,
            )
        recipient_ids = {
            project.created_by_id,
            project.assigned_user_id,
            *project.assignments.values_list('team_member__user_id', flat=True),
            *project.tasks.exclude(assigned_to_id=None).values_list('assigned_to_id', flat=True),
        }
        recipient_ids.discard(None)
        recipient_ids.discard(request.user.id)
        recipients = CustomUser.objects.filter(pk__in=recipient_ids, is_active=True)
        audience_label = project.name
    elif audience == 'people':
        raw_ids = data.get('recipient_ids') or []
        if not isinstance(raw_ids, list):
            return JsonResponse({'success': False, 'message': 'Choose one or more recipients.'}, status=400)
        try:
            requested_ids = {int(value) for value in raw_ids}
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': 'The recipient selection is invalid.'}, status=400)
        requested_ids.discard(request.user.id)
        recipients = _message_recipients_for(request.user).filter(pk__in=requested_ids)
        if recipients.count() != len(requested_ids):
            return JsonResponse(
                {'success': False, 'message': 'One or more recipients are outside your messaging permissions.'},
                status=403,
            )
        audience_label = 'selected recipients'
    else:
        return JsonResponse({'success': False, 'message': 'Choose people or a project team.'}, status=400)

    recipient_ids = list(recipients.values_list('id', flat=True)[:250])
    if not recipient_ids:
        return JsonResponse({'success': False, 'message': 'No other active team members were found.'}, status=400)

    with transaction.atomic():
        ChatMessage.objects.bulk_create([
            ChatMessage(
                sender=request.user,
                recipient_id=recipient_id,
                message=message_text,
                submission=None,
            )
            for recipient_id in recipient_ids
        ])

    return JsonResponse({
        'success': True,
        'recipient_count': len(recipient_ids),
        'message': f'Broadcast sent to {len(recipient_ids)} member(s) of {audience_label}.',
    })


@login_required
@require_http_methods(["POST"])
def broadcast_message(request):
    """Broadcast a message or multiple messages to selected recipients"""
    try:
        # Determine content type
        if request.content_type and 'multipart/form-data' in request.content_type:
            message_id = request.POST.get('message_id')
            recipient_id = request.POST.get('recipient_id')
            additional_message = request.POST.get('message', '').strip()
        else:
            data = json.loads(request.body)
            message_id = data.get('message_id')
            recipient_id = data.get('recipient_id')
            additional_message = data.get('message', '').strip()
        
        if not message_id or not recipient_id:
            return JsonResponse({
                'success': False,
                'message': 'Message ID and recipient ID are required'
            }, status=400)
        
        # Get the original message
        original_message = get_object_or_404(ChatMessage, id=message_id)
        
        # Permission check: user must be sender or recipient of original message
        if original_message.sender_id != request.user.id and original_message.recipient_id != request.user.id:
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to broadcast this message'
            }, status=403)
        
        # Get recipient
        recipient = get_object_or_404(CustomUser, id=recipient_id, is_active=True)
        
        # Permission check: sender and recipient should be staff/admin
        if not _can_send_staff_messages(request.user) or recipient.role not in MESSAGE_ROLES:
            return JsonResponse({
                'success': False,
                'message': 'Only staff members can broadcast messages'
            }, status=403)
        
        # Create new message with broadcasted content
        # If no additional message provided, forward original message text
        message_text = additional_message if additional_message else original_message.message
        
        new_message = ChatMessage.objects.create(
            sender=request.user,
            recipient=recipient,
            message=message_text,
            submission=None,
            attachment=original_message.attachment if not additional_message else None  # Forward attachment only if no new message
        )
        
        print(f"[BROADCAST] Message {original_message.id} broadcasted to {recipient.id} from {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'message_id': new_message.id,
            'timestamp': new_message.timestamp.isoformat(),
            'message': 'Message broadcasted successfully'
        })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        print(f"[BROADCAST] Error: {str(e)}")
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


@login_required
@require_http_methods(["GET"])
def download_message_attachment(request, message_id):
    """Download attachment from a message - with security checks"""
    try:
        # Get the message
        message = get_object_or_404(ChatMessage, id=message_id)
        
        print(f"[DEBUG] Download request - Message ID: {message_id}, User: {request.user}")
        print(f"[DEBUG] Message sender: {message.sender}, Recipient: {message.recipient}, Current user: {request.user}")
        
        # Security check: User must be either sender or recipient
        if request.user != message.sender and request.user != message.recipient:
            print(f"[DEBUG] Permission denied - user not sender or recipient")
            return JsonResponse({
                'success': False,
                'message': 'Permission denied'
            }, status=403)
        
        # Check if attachment exists
        if not message.attachment:
            print(f"[DEBUG] No attachment on message {message_id}")
            return JsonResponse({
                'success': False,
                'message': 'No attachment found'
            }, status=404)
        
        print(f"[DEBUG] Attachment found: {message.attachment}, Name: {message.attachment.name}")
        
        # Get file from the FileField
        try:
            # Read file content directly from the FileField
            file_content = message.attachment.read()
            file_name = os.path.basename(message.attachment.name)
            
            print(f"[DEBUG] File read successfully - Name: {file_name}, Size: {len(file_content)} bytes")
            
            # Determine content type
            import mimetypes
            content_type, _ = mimetypes.guess_type(file_name)
            if not content_type:
                content_type = 'application/octet-stream'
            
            print(f"[DEBUG] Content type: {content_type}")
            
            # Create response with file content
            response = FileResponse(
                io.BytesIO(file_content),
                as_attachment=True,
                filename=file_name,
                content_type=content_type
            )
            response['Content-Length'] = len(file_content)
            print(f"[DEBUG] FileResponse created and returned")
            return response
            
        except Exception as read_error:
            # If reading from FileField fails, try filesystem path
            print(f"[DEBUG] FileField read error: {read_error}, trying filesystem path")
            from django.conf import settings
            
            if hasattr(message.attachment, 'path'):
                file_path = message.attachment.path
            else:
                file_path = os.path.join(settings.MEDIA_ROOT, str(message.attachment))
            
            print(f"[DEBUG] File path: {file_path}, Exists: {os.path.exists(file_path)}")
            
            if not os.path.exists(file_path):
                return JsonResponse({
                    'success': False,
                    'message': f'File not found'
                }, status=404)
            
            if not os.access(file_path, os.R_OK):
                return JsonResponse({
                    'success': False,
                    'message': 'File is not readable'
                }, status=403)
            
            file_name = os.path.basename(file_path)
            
            # Determine content type
            import mimetypes
            content_type, _ = mimetypes.guess_type(file_name)
            if not content_type:
                content_type = 'application/octet-stream'
            
            with open(file_path, 'rb') as f:
                file_content = f.read()
                response = FileResponse(
                    io.BytesIO(file_content),
                    as_attachment=True,
                    filename=file_name,
                    content_type=content_type
                )
                response['Content-Length'] = len(file_content)
                return response
    
    except Exception as e:
        print(f"[DEBUG] Download error: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error: {str(e)}'
        }, status=500)
