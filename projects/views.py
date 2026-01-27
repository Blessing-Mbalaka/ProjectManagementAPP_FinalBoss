# projects/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .models import DailyTask, StudentProfile, Submission, Notification, Meeting, ChatMessage, Project, Assignment, TeamMember, Task
from users.models import CustomUser
from .forms import DailyTaskForm, StudentProfileForm, SubmissionForm, FeedbackReplyForm, MeetingForm, ChatForm, ProjectForm, AssignmentForm, FileUploadForm
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import date
from django.utils.timezone import now
from django.contrib import messages
from django.urls import reverse
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
from django.contrib.auth import get_user_model
from manager.models import LearningContent, Template
from django.db.models import Q
from django.utils import timezone
from adminpanel.models import Notification
from adminpanel.media_service import MediaService


@login_required
def dashboard(request):
    form = DailyTaskForm()
    tasks = DailyTask.objects.filter(user=request.user).order_by('-created_at')
    upload_form = FileUploadForm()

    now = timezone.now()
    base_qs = (Notification.objects
        .filter(
            Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=now),
            Q(expires_at__isnull=True)   | Q(expires_at__gt=now),
        )
        .filter(
            Q(audience='all') |
            Q(audience='role', audience_role=getattr(request.user, 'role', None)) |
            Q(audience='specific', recipients=request.user)
        )
        .select_related('created_by')
        .prefetch_related('recipients')
        .distinct()
    )
    my_notifications = base_qs.order_by('-is_pinned', '-created_at')[:10]

    if request.method == 'POST':
        form = DailyTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            return redirect('dashboard')

    return render(request, 'projects/dashboard.html', {
        'form': form,
        'daily_tasks': tasks,
        'upload_form': upload_form,
        'my_notifications': my_notifications,  # <-- ensure this is passed
    })




@login_required
def assignments(request):
    team_member = TeamMember.objects.filter(user=request.user).first()
    assignments = Assignment.objects.filter(team_member=team_member) if team_member else []

    return render(request, 'projects/assignments.html', {
        'assignments': assignments
    })



@login_required
def mark_task_done(request, task_id):
    task = get_object_or_404(DailyTask, id=task_id, user=request.user)
    task.is_done = True
    task.save()
    return redirect('dashboard')

@login_required
def delete_task(request, task_id):
    task = get_object_or_404(DailyTask, id=task_id, user=request.user)
    task.delete()
    return redirect('dashboard')

TASK_TYPES = ['UX/UI', 'Architecture', 'Frontend', 'Backend', 'Testing', 'Deployment', 'Paper', 'Book', 'Other']


@login_required
def staff_kanban(request):
    tasks = Task.objects.filter(
        Q(assigned_to=request.user) |
        Q(project__assignments__team_member__user=request.user)
    ).distinct().order_by('-created_at')

    grouped_tasks = {
        'todo': tasks.filter(status='todo'),
        'in_progress': tasks.filter(status='in_progress'),
        'review': tasks.filter(status='review'),
        'done': tasks.filter(status='done'),
    }

    projects = Project.objects.filter(
        Q(assigned_user=request.user) |
        Q(assignments__team_member__user=request.user)
    ).distinct()
    
    return render(request, 'projects/staff_kanban.html', {
        'grouped_tasks': grouped_tasks,
        'task_types': TASK_TYPES,
        'projects': projects
    })


@login_required
def staff_create_task(request):
    if request.method == 'POST':
        title = request.POST['title']
        status = request.POST['status']
        task_type = request.POST.get('task_type')
        priority = request.POST.get('priority')
        due_date_str = request.POST.get('due_date')
        project_id = request.POST.get('project_id')
        # project_name = request.POST.get('project_name', '').strip()

        # Convert due_date to a valid date or None
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                due_date = None  # fallback if date is badly formatted

        # project = None
        # if project_name:
        #     project, _ = Project.objects.get_or_create(name=project_name, defaults={'created_by': request.user})

        project = None
        if project_id:
            # Only allow projects the staff is actually assigned to
            project = Project.objects.filter(
                Q(assigned_user=request.user) |
                Q(assignments__team_member__user=request.user),
                id=project_id
            ).distinct().first()

        # Create the task
        Task.objects.create(
            title=title,
            status=status,
            task_type=task_type,
            priority=priority,
            due_date=due_date,
            assigned_to=request.user,
            created_by=request.user,
            project=project
        )
    return redirect('staff_kanban')


@login_required
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)

    if request.method == 'POST':
        project_name = request.POST.get('project_name', '').strip()
        task.title = request.POST.get('title', '').strip()
        task.status = request.POST.get('status')
        task.task_type = request.POST.get('task_type')
        task.priority = request.POST.get('priority')
        due_date_str = request.POST.get('due_date')

        # Convert due_date to valid date
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            except ValueError:
                due_date = None

        if project_name:
            project, _ = Project.objects.get_or_create(name=project_name, defaults={'created_by': request.user})
            task.project = project

        task.due_date = due_date
        task.save()

        return redirect('staff_kanban')

    return redirect('staff_kanban')

@csrf_exempt
@require_POST
@login_required
def update_task_status(request, task_id):
    try:
        data = json.loads(request.body)
        new_status = data.get('status')

        # Allow update if directly assigned OR assigned via team member
        task = get_object_or_404(Task, id=task_id)
        
        # Check if user is directly assigned or is a team member on the project
        is_directly_assigned = task.assigned_to == request.user
        is_team_member = task.project.assignments.filter(
            team_member__user=request.user
        ).exists()
        
        if not (is_directly_assigned or is_team_member):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        task.status = new_status
        task.save()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, assigned_to=request.user)
    if request.method == "POST":
        task.delete()
    return redirect('staff_kanban')  # Adjust redirect URL as needed


@login_required
def projects_review(request):
    return render(request, 'projects/projects_review.html')

@login_required
def ganttchart(request):
    if request.user.is_superuser or request.user.role == 'admin':
        tasks = Task.objects.all()
    else:
        tasks = Task.objects.filter(assigned_to=request.user)

    return render(request, 'projects/ganttchart.html', {'tasks': tasks})


def is_student(user):
    return user.role == 'student'

def is_student_or_supervisor(user):
    return user.role in ['student', 'admin', 'supervisor']

@login_required
@user_passes_test(is_student)
def student_dashboard(request):
    profile, created = StudentProfile.objects.get_or_create(user=request.user)

    # Handle profile form
    if request.method == 'POST' and 'update_profile' in request.POST:
        form = StudentProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            full_name = request.POST.get('name', '').strip()
            if full_name:
                parts = full_name.split()
                request.user.first_name = parts[0]
                request.user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
                request.user.save()
            return redirect('student_dashboard')
    else:
        form = StudentProfileForm(instance=profile)

    # Load submissions
    submissions = Submission.objects.filter(student=request.user).order_by('-created_at')
     # Filter feedback-provided submissions
    feedback_submissions = submissions.filter(status='Feedback Provided')

    # Submission form for modal
    submission_form = SubmissionForm()

    # Notifications
    notifications = Notification.objects.filter(recipients=request.user).order_by('-created_at')
    unread_count = 0

    #Meeting form
    meetings = Meeting.objects.filter(student=request.user).order_by('-date')
    meeting_form = MeetingForm()

    # Get messages with supervisor (received or sent to supervisor)
    from django.db.models import Q
    student_profile = StudentProfile.objects.get(user=request.user)
    chat_messages = ChatMessage.objects.filter(
        Q(sender=request.user, recipient=student_profile.supervisor) |  # Student sent to supervisor
        Q(sender=student_profile.supervisor, recipient=request.user)     # Supervisor sent to student
    ).order_by('timestamp') if student_profile.supervisor else ChatMessage.objects.none()
    chat_form = ChatForm()

    feedback_reply_form = FeedbackReplyForm()


    context = {
        'student': {
            'name': request.user.get_full_name(),
            'program': profile.program,
            'co_supervisor': profile.co_supervisor,
            'research_title': profile.research_title,
            'year': profile.year,
            'supervisor': profile.supervisor.get_full_name() if profile.supervisor else 'Not assigned',
            'progress': 65
        },
        'user': request.user,
        'form': form,
        'submissions': submissions,
        'submission_form': submission_form,
    }

        # Add feedback submissions to context
    context.update({
        'feedback_submissions': feedback_submissions,
    })

    context.update({
        'notifications': notifications,
        'unread_notification_count': unread_count
    })

    context.update({
    'meetings': meetings,
    'meeting_form': meeting_form,
    })

    context.update({
    'chat_messages': chat_messages,
    'chat_form': chat_form,
    'feedback_reply_form': feedback_reply_form
    })

    return render(request, 'projects/student_dashboard.html', context)

@login_required
@user_passes_test(is_student)
def submit_document(request):
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            # Assign version based on existing submissions
            existing = Submission.objects.filter(student=request.user, title=form.cleaned_data['title']).order_by('-version_number').first()
            version = existing.version_number + 1 if existing else 1

            submission = form.save(commit=False)
            submission.student = request.user
            submission.version_number = version
            submission.save()
            
            # Create SystemMedia record for the submission file
            if submission.file:
                MediaService.create_media_record(
                    file_obj=submission.file,
                    uploaded_by=request.user,
                    purpose='submission',
                    description=f"Submission: {submission.title} (v{submission.version_number})",
                    related_object=submission
                )

    return redirect('student_dashboard')


@login_required
@user_passes_test(is_student)
def submit_feedback_reply(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id, student=request.user)
    if request.method == 'POST':
        form = FeedbackReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.submission = submission
            reply.student = request.user
            reply.save()
    return redirect('student_dashboard')

@login_required
@user_passes_test(is_student)
def mark_notification_read(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, recipients=request.user)
    # Note: Notification model uses 'is_pinned' not 'is_read'
    # This endpoint acknowledges the notification without database changes
    return redirect('student_dashboard')

@login_required
@user_passes_test(is_student)
def submit_meeting_request(request):
    if request.method == 'POST':
        form = MeetingForm(request.POST)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.student = request.user
            meeting.save()
    return redirect('student_dashboard')

@login_required
@user_passes_test(is_student_or_supervisor)
def send_chat_message(request):
    if request.method == 'POST':
        print(f"\n=== SEND CHAT MESSAGE DEBUG ===")
        print(f"Sender: {request.user} (ID: {request.user.id}, Role: {request.user.role})")
        print(f"Request POST data: {request.POST}")
        
        form = ChatForm(request.POST)
        print(f"Form valid: {form.is_valid()}")
        
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            print(f"Message content: '{message.message}'")
            
            # Set recipient based on user role
            if request.user.role == 'student':
                # Students can only message their supervisor
                student_profile = StudentProfile.objects.get(user=request.user)
                message.recipient = student_profile.supervisor
                print(f"Student -> Supervisor: Recipient set to {message.recipient} (ID: {message.recipient.id if message.recipient else 'None'})")
            else:  # admin/supervisor
                # Supervisor messages the student they're viewing
                student_id = request.POST.get('student_id')
                print(f"Student ID from POST: {student_id}")
                
                if student_id:
                    student = CustomUser.objects.get(id=student_id)
                    print(f"Student found: {student} (ID: {student.id})")
                    
                    # Permission check: Supervisor can only message students they supervise
                    student_profile = StudentProfile.objects.get(user=student)
                    print(f"Student's supervisor: {student_profile.supervisor} (ID: {student_profile.supervisor.id if student_profile.supervisor else 'None'})")
                    print(f"Current supervisor: {request.user} (ID: {request.user.id})")
                    
                    if student_profile.supervisor == request.user:
                        message.recipient = student
                        print(f"✓ Permission granted - Recipient set to {message.recipient}")
                    else:
                        # Reject message if not authorized
                        message.recipient = None
                        print(f"✗ Permission denied - Supervisor not authorized for this student")
                else:
                    print(f"✗ No student_id provided in POST")
            
            if message.recipient:
                message.save()
                print(f"✓ Message SAVED (ID: {message.id})")
            else:
                print(f"✗ Message NOT saved - No recipient set")
        else:
            print(f"✗ Form errors: {form.errors}")
        
        print(f"=== END DEBUG ===\n")
    
    # Redirect based on user role
    if request.user.role == 'student':
        return redirect('student_dashboard')
    elif request.user.role == 'supervisor':
        # Supervisors redirect to supervisor portal
        student_id = request.POST.get('student_id')
        if student_id:
            return redirect('supervisor_student_detail', student_id=student_id)
        return redirect('supervisor_dashboard_portal')  # fallback
    else:  # admin
        # Admin redirects to old admin route
        student_id = request.POST.get('student_id')
        if student_id:
            return redirect('student_detail', student_id=student_id)
        return redirect('supervisor_dashboard')


@login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id, created_by=request.user)
    if request.method == 'POST':
        project.delete()
        messages.success(request, 'Project deleted successfully!')
        return redirect('dashboard')
    return render(request, 'projects/confirm_delete.html', {'project': project})

@login_required
def remove_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id, project__created_by=request.user)
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, f'{assignment.team_member} removed from the project!')
        return redirect('project_detail', project_id=assignment.project.id)
    return render(request, 'projects/confirm_remove.html', {'assignment': assignment})

@login_required
def team_dashboard(request):
    # Get all assignments for the current user
    assignments = Assignment.objects.filter(team_member__user=request.user)
    context = {
        'assignments': assignments
    }
    return render(request, 'projects/team_dashboard.html', context)



@login_required
def staff_elearning(request):
    resources = LearningContent.objects.all().order_by('-created_at')
    resource_types = LearningContent.objects.values_list('type', flat=True).distinct()

    selected_type = request.GET.get('type', 'All')
    search_query = request.GET.get('search', '').strip()

    if selected_type.lower() != "all":
        resources = resources.filter(type__icontains=selected_type)

    if search_query:
        resources = resources.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    return render(request, 'projects/elearning.html', {
        'resources': resources,
        'resource_types': resource_types,
        'selected_type': selected_type,
        'search_query': search_query,
    })


@login_required
def staff_templates(request):
    templates = Template.objects.all()
    search_query = request.GET.get('search', '').strip()

    if search_query:
        templates = templates.filter(title__icontains=search_query)

    template_categories = {}
    for t in templates:
        category = t.category or "Uncategorized"
        if category not in template_categories:
            template_categories[category] = []
        template_categories[category].append(t)

    return render(request, 'projects/templates.html', {
        'template_categories': template_categories,
        'search_query': search_query,
    })
