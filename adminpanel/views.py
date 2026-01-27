from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from users.models import CustomUser
from users.forms import CustomUserCreationForm
from .models import CostCentre, Expenditure, SupervisorProfile, SupervisorFeedback, Notification
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import csv
import io
from projects.models import Project, Submission, StudentProfile, Meeting, ChatMessage, Task, Assignment
from django.contrib.auth import get_user_model
from .forms import SupervisorFeedbackForm, NotificationForm, ProjectForm
from django.http import JsonResponse, HttpResponseBadRequest
from decimal import Decimal, InvalidOperation
from django.db.models import Sum, Count, Q
from collections import Counter
from django.db.models.functions import TruncMonth
from django.utils.dateparse import parse_date
from manager.models import Paper
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import models
from django.views.decorators.http import require_http_methods
from projects.models import StudentProfile
import csv
import io


@login_required
def admin_dashboard(request):
    return render(request, 'adminpanel/admin_dashboard.html')

@login_required
def app_kanban(request):
    phases = ["UX/UI", "Architecture", "Frontend", "Backend", "Testing", "Deployment"]
    return render(request, 'adminpanel/app_kanban.html', {'phases': phases})


@login_required
@user_passes_test(lambda u: u.role in ['admin', 'manager'])
def admin_ganttchart(request):
    projects = Project.objects.prefetch_related('tasks__subtasks')
    return render(request, 'adminpanel/admin_ganttchart.html', {'projects': projects})


def register_users(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            role = request.POST.get('role')

            # Prevent anyone from trying to register as an admin
            if role == 'admin':
                form.add_error(None, "You are not allowed to register as an admin.")
                return render(request, 'users/register.html', {'form': form})

            user = form.save(commit=False)
            user.role = role
            user.save()

            # Automatically create StudentProfile if role is student
            if role == 'student':
                supervisor = CustomUser.objects.filter(role='admin').first()
                StudentProfile.objects.create(user=user, supervisor=supervisor)

            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})


@login_required
def overview(request):
    User = get_user_model()
    users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')

    projects = Project.objects.prefetch_related(
        'tasks',
        'assignments__team_member__user'
    ).select_related('created_by', 'assigned_user')

    progress_list, status_list, type_list = [], [], []

    for p in projects:
        tasks = p.tasks.all()
        total = tasks.count()
        done = tasks.filter(status='done').count()
        p.progress = int((done / total) * 100) if total else 0

        status_list.append(p.status)         # 'planning' / 'in-progress' / 'on-hold' / 'completed'
        type_list.append(p.project_type)     # 'software' / 'paper' / 'book'
        progress_list.append(p.progress)

    status_counts = Counter(status_list)
    type_counts = Counter(type_list)

    bins = {'0–25%': 0, '26–50%': 0, '51–75%': 0, '76–100%': 0}
    for val in progress_list:
        if val <= 25:   bins['0–25%'] += 1
        elif val <= 50: bins['26–50%'] += 1
        elif val <= 75: bins['51–75%'] += 1
        else:           bins['76–100%'] += 1

    insights = {
        'by_status': status_counts,
        'by_type': type_counts,
        'progress_hist': bins,
    }

        # --- Notifications for the page ---
    now = timezone.now()
    recent_notifications = Notification.objects.filter(
        models.Q(scheduled_at__isnull=True) | models.Q(scheduled_at__lte=now),
        models.Q(expires_at__isnull=True)   | models.Q(expires_at__gt=now),
    ).order_by('-is_pinned', '-created_at')[:8]

    return render(request, 'adminpanel/overview.html', {
        'projects': projects,
        'users': users,
        'insights_json': json.dumps(insights),
        'recent_notifications': recent_notifications
    })



def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

@login_required
@user_passes_test(is_admin)
def manage_users(request):
    search = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')

    users = CustomUser.objects.exclude(role='admin')

    if search:
        users = users.filter(Q(username__icontains=search) | Q(email__icontains=search))
    if role_filter:
        users = users.filter(role=role_filter)

    role_totals = Counter(CustomUser.objects.exclude(role='admin').values_list('role', flat=True))
    role_labels = dict(CustomUser.ROLE_CHOICES)

        # 🛠️ Create a dict of user_id → pre-filled edit form
    edit_forms = {user.id: CustomUserCreationForm(instance=user) for user in users}

    return render(request, 'adminpanel/manage_users.html', {
        'users': users,
        'form': CustomUserCreationForm(),
        'edit_forms': edit_forms,
        'role_totals': role_totals,
        'role_counts': role_labels
    })


@login_required
@user_passes_test(is_admin)
def create_user(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = form.cleaned_data['role']
            password = form.cleaned_data['password1']
            user.set_password(password)
            user.save()
            # Send email to new user
            subject = "You've been registered on the Project Management System"
            message = f"""
            Hello {user.username},

            You have been successfully registered on the UJ Project Management Platform.

            🔑 Login Credentials:
            Username: {user.username}
            Password: {password}

            🔗 Login URL: https://django-project-app.lemonisland-3cb848d5.southafricanorth.azurecontainerapps.io

            Please change your password after your first login.

            Regards,
            UJ Project Management Admin Team
            """.strip()

            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            messages.success(request, f"User {user.username} created and notified via email.")
        else:
            print(form.errors)
            messages.error(request, "Failed to create user. Please check the form.")
    return redirect('manage_users')


@login_required
@user_passes_test(is_admin)
def activate_user(request, user_id):
    user = get_object_or_404(CustomUser, pk=user_id)
    user.is_active = True
    user.save()
    messages.success(request, f"{user.username} activated.")
    return redirect('manage_users')

@login_required
@user_passes_test(is_admin)
def deactivate_user(request, user_id):
    user = get_object_or_404(CustomUser, pk=user_id)
    user.is_active = False
    user.save()
    messages.warning(request, f"{user.username} deactivated.")
    return redirect('manage_users')

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    user = get_object_or_404(CustomUser, pk=user_id)
    if user.role != 'admin':
        user.delete()
        messages.error(request, f"{user.username} deleted.")
    else:
        messages.error(request, "You cannot delete an admin.")
    return redirect('manage_users')

# @login_required
# @user_passes_test(is_admin)
# def edit_user(request, user_id):
#     user = get_object_or_404(CustomUser, pk=user_id)

#     if request.method == 'POST':
#         form = CustomUserCreationForm(request.POST, instance=user)
#         if form.is_valid():
#             form.save()
#             messages.success(request, f"{user.username} updated.")
#             return redirect('manage_users')
#         else:
#             messages.error(request, "Something went wrong updating the user.")
#     else:
#         form = CustomUserCreationForm(instance=user)

#     return render(request, 'adminpanel/partials/edit_user_form.html', {
#         'form': form,
#         'user_id': user.id,
#         'user_obj': user
#     })

@login_required
@user_passes_test(is_admin)
def edit_user(request, user_id):
    user = get_object_or_404(CustomUser, pk=user_id)

    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.email = request.POST.get('email')
        user.role = request.POST.get('role')

        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 and password1 == password2:
            user.set_password(password1)

        user.save()
        messages.success(request, f"{user.username} updated.")
    else:
        messages.error(request, "Invalid request.")
    return redirect('manage_users')



@login_required
@user_passes_test(lambda u: u.role == 'admin')
def assign_project(request):
    """Assign an existing project to a staff member"""
    if request.method == 'POST':
        project_id = request.POST.get('project_id')
        assigned_user_id = request.POST.get('assigned_user')
        description = request.POST.get('description', '')
        
        # Validate project exists
        project = get_object_or_404(Project, id=project_id)
        
        # Validate user exists
        assigned_user = get_object_or_404(get_user_model(), id=assigned_user_id)
        
        # Update project assignment and description
        project.assigned_user = assigned_user
        if description:
            project.description = description
        project.save()
        
        messages.success(request, f"Project '{project.name}' assigned to {assigned_user.get_full_name() or assigned_user.username}!")
        return redirect('overview')
    
    # GET request - provide list of projects and users
    projects = Project.objects.all().order_by('-created_at')
    users = get_user_model().objects.filter(is_active=True).order_by('first_name', 'last_name')
    
    return render(request, 'adminpanel/overview.html', {
        'projects': projects,
        'users': users
    })
    
@login_required
def gantt_data_api(request):
    projects = Project.objects.prefetch_related('tasks').all()
    data = []

    for project in projects:
        for task in project.tasks.all():
            data.append({
                "id": f"T{task.id}",
                "name": task.title,
                "resource": project.name,
                "start": task.created_at.strftime('%Y-%m-%d'),
                "end": task.due_date.strftime('%Y-%m-%d') if task.due_date else None,
                "progress": 0 if task.status == 'todo' else 25 if task.status == 'in_progress' else 75 if task.status == 'review' else 100,
                "dependencies": f"T{task.parent_task.id}" if task.parent_task else None,
            })
    return JsonResponse(data, safe=False)


@login_required
def project_task_detail(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    tasks = Task.objects.filter(project=project)
    return render(request, 'adminpanel/project_tasks.html', {'project': project, 'tasks': tasks})

@csrf_exempt
def update_task_progress(request, task_id):
    if request.method == "POST":
        data = json.loads(request.body)
        try:
            task = Task.objects.get(id=task_id)
            task.progress = min(max(int(data["progress"]), 0), 100)
            task.save()
            return JsonResponse({"success": True})
        except Task.DoesNotExist:
            return JsonResponse({"error": "Task not found"}, status=404)
    return JsonResponse({"error": "Invalid request"}, status=400)

@login_required
def finance(request):
    cost_centres = CostCentre.objects.all()
    all_expenditures = Expenditure.objects.select_related('cost_centre').all()

    # Total spent per category
    category_totals = (
        Expenditure.objects.values('category')
        .annotate(total=Sum('amount'))
        .order_by('category')
    )

    monthly_totals = (
        Expenditure.objects
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    return render(request, 'adminpanel/finance.html', {
        'cost_centres': cost_centres,
        'all_expenditures': all_expenditures,
        'category_totals': category_totals,
        'monthly_totals': monthly_totals,
    })

@login_required
def add_cost_centre(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        received = request.POST.get('received')
        if name and received:
            CostCentre.objects.create(
                name=name,
                total_received=received,
                total_spent=0
            )
            return JsonResponse({'message': 'Cost Centre added successfully'})
        return HttpResponseBadRequest('Missing fields')
    return HttpResponseBadRequest('Invalid request')
    
@login_required
def add_expenditure(request):
    if request.method == 'POST':
        cost_centre_id = request.POST.get('cost_centre_id')
        month = request.POST.get('month')
        name = request.POST.get('name')
        category = request.POST.get('category')

        # Safely convert numeric fields
        try:
            amount = Decimal(request.POST.get('amount', '0') or '0.00')
            oracle = Decimal(request.POST.get('oracle_balance', '0') or '0.00')
        except InvalidOperation:
            return HttpResponseBadRequest("Invalid number format")

        cost_centre = CostCentre.objects.get(id=cost_centre_id)
        Expenditure.objects.create(
            cost_centre=cost_centre,
            month=month,
            name=name,
            category=category,
            amount=amount,
            oracle_balance=oracle
        )
        return redirect('finance')


@login_required
def get_expenditures(request, cost_centre_id):
    cost_centre = CostCentre.objects.get(id=cost_centre_id)
    expenditures = cost_centre.expenditures.all()
    data = []
    for exp in expenditures:
        data.append({
            'month': exp.month,
            'name': exp.name,
            'category': exp.category,
            'amount': str(exp.amount),
            'opening_balance': str(exp.opening_balance),
            'closing_balance': str(exp.closing_balance),
            'oracle_balance': str(exp.oracle_balance),
        })
    return JsonResponse({'expenditures': data})

@login_required
def delete_cost_centre(request, pk):
    cost_centre = get_object_or_404(CostCentre, pk=pk)
    if request.method == 'POST':
        cost_centre.delete()
        return redirect('finance')
    return render(request, 'adminpanel/confirm_delete.html', {'cost_centre': cost_centre})

@login_required
def edit_cost_centre(request, pk):
    cost_centre = get_object_or_404(CostCentre, pk=pk)
    if request.method == 'POST':
        cost_centre.name = request.POST.get('name')
        
        # Validate and convert total_received with error handling
        try:
            total_received_str = request.POST.get('total_received', '0')
            if not total_received_str or total_received_str.strip() == '':
                total_received_str = '0.00'
            total_received = Decimal(total_received_str)
            # Validate decimal places (max 2)
            if total_received.as_tuple().exponent < -2:
                messages.error(request, 'Please enter a valid number with up to 2 decimal places')
                return redirect('finance')
            cost_centre.total_received = total_received
        except InvalidOperation:
            messages.error(request, 'Invalid amount: please enter a valid number')
            return redirect('finance')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount format')
            return redirect('finance')
        
        try:
            cost_centre.save()
            messages.success(request, 'Cost Centre updated successfully')
        except ValidationError as e:
            messages.error(request, f'Error saving Cost Centre: {e}')
        
        return redirect('finance')
    return redirect('finance')  # fallback if GET request

@login_required
def edit_expenditure(request, pk):
    expenditure = get_object_or_404(Expenditure, pk=pk)
    if request.method == 'POST':
        expenditure.month = request.POST.get('month')
        expenditure.name = request.POST.get('name')
        expenditure.category = request.POST.get('category')
        
        # Validate and convert amount with error handling
        try:
            amount_str = request.POST.get('amount', '0')
            if not amount_str or amount_str.strip() == '':
                amount_str = '0.00'
            amount = Decimal(amount_str)
            # Validate decimal places (max 2)
            if amount.as_tuple().exponent < -2:
                messages.error(request, 'Please enter a valid number with up to 2 decimal places')
                return redirect('finance')
            expenditure.amount = amount
        except InvalidOperation:
            messages.error(request, 'Invalid amount: please enter a valid number')
            return redirect('finance')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid amount format')
            return redirect('finance')
        
        # Validate and convert oracle_balance with error handling
        try:
            oracle_str = request.POST.get('oracle_balance', '0')
            if not oracle_str or oracle_str.strip() == '':
                oracle_str = '0.00'
            oracle_balance = Decimal(oracle_str)
            # Validate decimal places (max 2)
            if oracle_balance.as_tuple().exponent < -2:
                messages.error(request, 'Please enter a valid Oracle balance with up to 2 decimal places')
                return redirect('finance')
            expenditure.oracle_balance = oracle_balance
        except InvalidOperation:
            messages.error(request, 'Invalid Oracle balance: please enter a valid number')
            return redirect('finance')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid Oracle balance format')
            return redirect('finance')
        
        try:
            expenditure.save()
            messages.success(request, 'Expenditure updated successfully')
        except ValidationError as e:
            messages.error(request, f'Error saving Expenditure: {e}')
        except InvalidOperation as e:
            messages.error(request, 'Error calculating balance: invalid number format')
        
        return redirect('finance')
    return redirect('finance')

@login_required
def delete_expenditure(request, pk):
    expenditure = get_object_or_404(Expenditure, pk=pk)
    if request.method == 'POST':
        expenditure.delete()
        return redirect('finance')
    return redirect('finance')


@login_required
def admin_kanban(request):
    return render(request, 'adminpanel/admin_kanban.html')

# @login_required
# def supervisor_dashboard(request):
#     return render(request, 'adminpanel/supervisor_dashboard.html')

def is_supervisor(user):
    return user.is_authenticated and user.role == 'admin'


@login_required
@user_passes_test(is_supervisor)
def provide_feedback(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    supervisor = request.user.supervisorprofile
    if request.method == 'POST':
        form = SupervisorFeedbackForm(request.POST, request.FILES)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.submission = submission
            feedback.supervisor = supervisor
            feedback.save()

            # Optionally update submission status directly
            submission.status = feedback.status
            submission.feedback_text = feedback.comments
            if feedback.uploaded_file:
                submission.feedback_file = feedback.uploaded_file
            submission.save()

            return redirect('supervisor_dashboard')  # or your submissions page
    else:
        form = SupervisorFeedbackForm()

    return render(request, 'adminpanel/provide_feedback.html', {
        'form': form,
        'submission': submission
    })

@login_required
@user_passes_test(lambda u: u.role == 'admin')
def supervisor_dashboard(request):
    supervisor = request.user
    student_profiles = StudentProfile.objects.filter(supervisor=supervisor).select_related('user')

    return render(request, 'adminpanel/supervisor_dashboard.html', {
        'student_profiles': student_profiles
    })

@login_required
@user_passes_test(lambda u: u.role == 'admin')
def student_detail_view(request, student_id):
    student_user = CustomUser.objects.get(id=student_id)
    student_profile = StudentProfile.objects.get(user=student_user)
    submission_history = Submission.objects.filter(student=student_user)
    meeting_history = Meeting.objects.filter(student=student_user)
    form = SupervisorFeedbackForm()

    return render(request, 'adminpanel/student_detail.html', {
        'student_user': student_user,
        'student_profile': student_profile,
        'submission_history': submission_history,
        'meeting_history': meeting_history,
        'form' : form
    })


# @login_required
# @user_passes_test(lambda u: u.role == 'admin')
# def supervisor_dashboard(request):
#     supervisor = request.user  # This is the CustomUser with role='admin'

#     # Step 1: Find students supervised by this admin
#     supervised_student_users = StudentProfile.objects.filter(supervisor=supervisor).values_list('user', flat=True)

#     # Step 2: Filter submissions for those student users
#     submissions = Submission.objects.filter(student__in=supervised_student_users)

#     meetings = Meeting.objects.filter(student__in=supervised_student_users)
#     chat_messages = ChatMessage.objects.filter(sender=request.user)
#     # chat_form = ChatForm()
#     # meeting_form = MeetingRequestForm()

#     return render(request, 'adminpanel/supervisor_dashboard.html', {
#         'submissions': submissions,
#         'meetings': meetings,
#         'chat_messages': chat_messages,
#         # 'chat_form': chat_form,
#         # 'meeting_form': meeting_form,
#     })

@login_required
def admin_journal(request):
    internal_papers = Paper.objects.filter(internal_external='internal').order_by('-updated_at')
    external_papers = Paper.objects.filter(internal_external='external').order_by('-updated_at')
    
    return render(request, 'adminpanel/admin_journal.html', {
        'internal_papers': internal_papers,
        'external_papers': external_papers,
    })

@login_required
def admin_book(request):
    return render(request, 'adminpanel/admin_book.html')

# def admin_required(view_func):
#     return user_passes_test(lambda u: u.is_authenticated and u.role == 'admin')(view_func)

def admin_required(view_func):
    return user_passes_test(
        lambda u: u.is_authenticated and u.role == 'admin',
        login_url='/login/'  #  app login page
    )(view_func)

@admin_required
def admin_user_kanban(request, user_id):
    user = get_object_or_404(get_user_model(), id=user_id)
    tasks = Task.objects.filter(assigned_to=user)

    # Group by status
    task_data = {
        'todo': tasks.filter(status='todo'),
        'in_progress': tasks.filter(status='in_progress'),
        'review': tasks.filter(status='review'),
        'done': tasks.filter(status='done'),
    }

    return render(request, 'adminpanel/partials/user_kanban.html', {
        'user': user,
        'task_data': task_data
    })

@login_required
@user_passes_test(lambda u: u.role == 'admin')
def assign_project_manager(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if request.method == 'POST':
        user_id = request.POST.get('manager_id')
        manager = get_object_or_404(get_user_model(), id=user_id, role='manager')
        project.assigned_user = manager
        project.save()
        return redirect('overview')  # or admin_dashboard
    managers = get_user_model().objects.filter(role='manager')
    return render(request, 'adminpanel/assign_project.html', {'project': project, 'managers': managers})


# adminpanel/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import redirect
from .forms import NotificationForm
from .models import Notification
from users.models import CustomUser  # adjust if your user model is elsewhere

def is_admin(user):
    return getattr(user, 'role', '') == 'admin'

@login_required
@user_passes_test(is_admin)
def create_notification(request):
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            notif = form.save(commit=False)
            notif.created_by = request.user
            notif.save()
            form.save_m2m()
            messages.success(request, "Notification created.")
        else:
            # stash errors to display on the overview page modal
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"{field}: {e}")
        # send back to Overview (where the modal lives)
        return redirect('overview')
    return redirect('overview')
@login_required
@user_passes_test(lambda u: u.role == 'admin')
@require_http_methods(["POST"])
def load_student_manual(request):
    """Load a single student manually via modal form (non-destructive)"""
    try:
        email = request.POST.get('email', '').strip()
        program = request.POST.get('program', '').strip()
        year = request.POST.get('year', '').strip()
        research_title = request.POST.get('research_title', '').strip()
        
        if not all([email, program, year, research_title]):
            messages.error(request, "All fields are required.")
            return redirect('overview')
        
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            messages.error(request, f"User with email '{email}' does not exist.")
            return redirect('overview')
        
        # Non-destructive: only create or update if new
        student_profile, created = StudentProfile.objects.get_or_create(
            user=user,
            defaults={
                'supervisor': request.user,
                'program': program,
                'year': year,
                'research_title': research_title,
                'co_supervisor': request.POST.get('co_supervisor', '').strip() or None,
            }
        )
        
        if created:
            messages.success(request, f"Added {user.get_full_name()} as supervised student.")
        else:
            messages.warning(request, f"{user.get_full_name()} already registered.")
        
        return redirect('supervisor_dashboard')
        
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('overview')


@login_required
@user_passes_test(lambda u: u.role == 'admin')
@require_http_methods(["POST"])
def load_students_csv(request):
    """Load multiple students from CSV file (non-destructive)"""
    try:
        if 'csv_file' not in request.FILES:
            messages.error(request, "No CSV file provided.")
            return redirect('overview')
        
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a CSV file.")
            return redirect('overview')
        
        decoded_file = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded_file))
        
        required_fields = {'email', 'program', 'year', 'research_title'}
        if not required_fields.issubset(set(reader.fieldnames or [])):
            messages.error(request, "CSV missing required columns: email, program, year, research_title")
            return redirect('overview')
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        for row_num, row in enumerate(reader, start=2):
            try:
                email = row.get('email', '').strip()
                program = row.get('program', '').strip()
                year = row.get('year', '').strip()
                research_title = row.get('research_title', '').strip()
                
                if not all([email, program, year, research_title]):
                    errors.append(f"Row {row_num}: Missing required fields")
                    continue
                
                try:
                    user = CustomUser.objects.get(email=email)
                except CustomUser.DoesNotExist:
                    errors.append(f"Row {row_num}: User '{email}' not found")
                    continue
                
                student_profile, created = StudentProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'supervisor': request.user,
                        'program': program,
                        'year': year,
                        'research_title': research_title,
                        'co_supervisor': row.get('co_supervisor', '').strip() or None,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        if created_count > 0:
            messages.success(request, f"Added {created_count} new student(s).")
        if skipped_count > 0:
            messages.info(request, f"Skipped {skipped_count} existing student(s).")
        
        for error in errors[:5]:
            messages.error(request, error)
        
        return redirect('supervisor_dashboard')
        
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('overview')


# ============================================================================
# PROJECT MANAGEMENT VIEWS
# ============================================================================

@login_required
@user_passes_test(lambda u: u.role == 'admin')
def create_project(request):
    """Create a new project via AJAX or form submission"""
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Project created successfully', 'project_id': project.id})
            else:
                messages.success(request, f"Project '{project.name}' created successfully!")
                return redirect('overview')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
            else:
                messages.error(request, "Form validation failed.")
                return redirect('overview')
    
    form = ProjectForm()
    return render(request, 'adminpanel/partials/addprojects.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.role == 'admin')
def update_project(request, project_id):
    """Update an existing project"""
    project = get_object_or_404(Project, id=project_id)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Project updated successfully'})
            else:
                messages.success(request, f"Project '{project.name}' updated successfully!")
                return redirect('overview')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors})
            else:
                messages.error(request, "Form validation failed.")
                return redirect('overview')
    
    form = ProjectForm(instance=project)
    return render(request, 'adminpanel/partials/addprojects.html', {'form': form, 'editing': True})


@login_required
@user_passes_test(lambda u: u.role == 'admin')
def delete_project(request, project_id):
    """Delete a project"""
    project = get_object_or_404(Project, id=project_id)
    project_name = project.name
    
    if request.method == 'POST':
        try:
            project.delete()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f"Project '{project_name}' deleted successfully"})
            else:
                messages.success(request, f"Project '{project_name}' deleted successfully!")
                return redirect('overview')
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f"Error deleting project: {str(e)}"})
            else:
                messages.error(request, f"Error deleting project: {str(e)}")
                return redirect('overview')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    return redirect('overview')


@login_required
@user_passes_test(lambda u: u.role == 'admin')
def get_projects_json(request):
    """Get all projects as JSON for dropdown population"""
    projects = Project.objects.all().values('id', 'name', 'description', 'project_type', 'status', 'due_date').order_by('-created_at')
    return JsonResponse({'projects': list(projects)})
