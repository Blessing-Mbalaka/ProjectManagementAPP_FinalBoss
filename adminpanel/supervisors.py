"""
Supervisor Portal Views
Dedicated views for supervisor role users with isolated routing
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.db.models import Q, Prefetch
from projects.models import ChatMessage, StudentProfile
from users.models import CustomUser


def is_supervisor(user):
    """Check if user is a supervisor"""
    return user.role == 'supervisor'


@login_required
def supervisor_dashboard(request):
    """
    Supervisor dashboard - Shows all supervised students
    Only accessible to users with role='supervisor'
    """
    if not is_supervisor(request.user):
        return redirect('admin_dashboard')
    
    supervisor = request.user
    student_profiles = StudentProfile.objects.filter(
        supervisor=supervisor
    ).select_related('user').order_by('user__last_name')
    
    context = {
        'student_profiles': student_profiles,
        'unread_message_count': ChatMessage.objects.filter(
            recipient=request.user
        ).count(),
        'active_submissions': 0,  # Can be calculated from student submissions if needed
    }
    
    return render(request, 'supervisors/dashboard.html', context)


@login_required
def supervisor_messages(request):
    """
    Supervisor messages view - Shows all conversations with students
    Only accessible to users with role='supervisor'
    """
    if not is_supervisor(request.user):
        return redirect('admin_dashboard')
    
    supervisor = request.user
    
    # Get all students supervised by this supervisor
    supervised_students = StudentProfile.objects.filter(
        supervisor=supervisor
    ).select_related('user').order_by('user__last_name')
    
    # Get conversations with last message for each student
    conversations = []
    for student_profile in supervised_students:
        last_message = ChatMessage.objects.filter(
            Q(sender=student_profile.user, recipient=supervisor) |
            Q(sender=supervisor, recipient=student_profile.user)
        ).order_by('-timestamp').first()
        
        conversations.append((student_profile, last_message))
    
    context = {
        'conversations': conversations,
    }
    
    return render(request, 'supervisors/messages.html', context)


@login_required
def supervisor_student_detail(request, student_id):
    """
    Supervisor view of individual student detail page
    Only accessible to the supervisor assigned to this student
    """
    if not is_supervisor(request.user):
        return redirect('admin_dashboard')
    
    try:
        student_user = CustomUser.objects.get(id=student_id)
        student_profile = StudentProfile.objects.get(user=student_user)
    except (CustomUser.DoesNotExist, StudentProfile.DoesNotExist):
        raise Http404("Student not found.")
    
    # Permission check: Only allow supervisors to view their own supervised students
    if student_profile.supervisor != request.user:
        raise Http404("You don't have permission to view this student's details.")
    
    # Get chat messages in conversation
    chat_messages = ChatMessage.objects.filter(
        Q(sender=student_user, recipient=request.user) |
        Q(sender=request.user, recipient=student_user)
    ).order_by('timestamp')
    
    context = {
        'student_profile': student_profile,
        'student_user': student_user,
        'chat_messages': chat_messages,
        'submissions_count': 0,  # Can be calculated if needed
    }
    
    return render(request, 'supervisors/student_detail.html', context)
