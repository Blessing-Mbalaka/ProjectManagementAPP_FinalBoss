from django.shortcuts import render, redirect, get_object_or_404

#Here  is the Default Django User_ROLE_VALIDATION.
from django.contrib.auth.decorators import login_required, user_passes_test

from users.models import CustomUser
from users.forms import CustomUserCreationForm
from manager.models import Book, Chapter
from .models import CostCentre, Expenditure, SupervisorProfile, SupervisorFeedback, Notification
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import csv
from .media_service import MediaService
import io
from projects.models import Project, Submission, StudentProfile, Meeting, ChatMessage, Task, Assignment
from django.contrib.auth import get_user_model
from .forms import SupervisorFeedbackForm, NotificationForm, ProjectForm
from projects.forms import ChatForm
from django.http import JsonResponse, HttpResponseBadRequest
from decimal import Decimal, InvalidOperation
from django.db.models import Sum, Count, Q
from collections import Counter, defaultdict
from django.db.models.functions import TruncMonth
from django.utils.dateparse import parse_date
from manager.models import Paper
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import models, connection
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from projects.models import StudentProfile
import csv
import io


def safe_decimal(value, default=Decimal('0.00')):
    if value is None:
        return default

    try:
        dec = value if isinstance(value, Decimal) else Decimal(str(value))
        if dec.is_nan() or dec.is_infinite():
            return default
        return dec
    except (InvalidOperation, TypeError, ValueError):
        return default


def decimal_to_float(value):
    try:
        return float(safe_decimal(value))
    except (TypeError, ValueError, InvalidOperation, OverflowError):
        return 0.0


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

        #Create a dict of user_id → pre-filled edit form
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
@login_required
@login_required
def finance(request):
    from django.db import connection

    payment_summary = defaultdict(lambda: {'count': 0, 'total': Decimal('0.00')})
    payments_by_cc = defaultdict(list)
    cost_centres_map = {}
    all_expenditures = []
    expenditure_summary = defaultdict(lambda: Decimal('0.00'))

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, cost_centre_id, amount, description, payment_date
            FROM adminpanel_costcentrepayment
            ORDER BY payment_date DESC
        """)
        for payment_id, cc_id, amount, description, payment_date in cursor.fetchall():
            amount_dec = safe_decimal(amount)
            summary = payment_summary[cc_id]
            summary['count'] += 1
            summary['total'] += amount_dec
            payments_by_cc[cc_id].append({
                'id': payment_id,
                'amount': decimal_to_float(amount_dec),
                'description': description,
                'payment_date': payment_date
            })

        cursor.execute("SELECT id, name FROM adminpanel_costcentre ORDER BY name")
        for cc_id, name in cursor.fetchall():
            cost_centres_map[cc_id] = {'id': cc_id, 'name': name}

        cursor.execute("""
            SELECT id, cost_centre_id, month, name, category, amount, opening_balance, closing_balance, oracle_balance
            FROM adminpanel_expenditure
            ORDER BY id DESC
        """)
        for exp_id, cc_id, month, name, category, amount, opening_balance, closing_balance, oracle_balance in cursor.fetchall():
            amount_dec = safe_decimal(amount)
            opening_dec = safe_decimal(opening_balance)
            closing_dec = safe_decimal(closing_balance)
            oracle_dec = safe_decimal(oracle_balance)

            expenditure_summary[cc_id] += amount_dec

            cc_info = cost_centres_map.get(cc_id)
            if not cc_info:
                cc_info = {'id': cc_id, 'name': 'Unknown'}
                cost_centres_map[cc_id] = cc_info

            all_expenditures.append({
                'id': exp_id,
                'cost_centre': cc_info,
                'cost_centre_id': cc_id,
                'month': month,
                'name': name,
                'category': category,
                'amount': decimal_to_float(amount_dec),
                'opening_balance': decimal_to_float(opening_dec),
                'closing_balance': decimal_to_float(closing_dec),
                'oracle_balance': decimal_to_float(oracle_dec)
            })

    cost_centres = []
    for cc_id, info in cost_centres_map.items():
        total_received = payment_summary[cc_id]['total']
        total_spent = expenditure_summary[cc_id]
        total_remaining = total_received - total_spent

        info.update({
            'total_received': decimal_to_float(total_received),
            'total_spent': decimal_to_float(total_spent),
            'total_remaining': decimal_to_float(total_remaining),
            'payment_count': payment_summary[cc_id]['count']
        })
        cost_centres.append(info)

    category_totals = {}
    monthly_totals = {}
    for exp in all_expenditures:
        category = exp['category']
        category_totals.setdefault(category, 0)
        category_totals[category] += exp['amount']

        month = exp['month']
        monthly_totals.setdefault(month, 0)
        monthly_totals[month] += exp['amount']

    return render(request, 'adminpanel/finance.html', {
        'cost_centres': cost_centres,
        'all_expenditures': all_expenditures,
        'category_totals': category_totals,
        'monthly_totals': monthly_totals,
        'category_choices': Expenditure.EXPENSE_CATEGORY_CHOICES,
        'payments_by_cc': payments_by_cc,
    })

@login_required
@login_required
def add_cost_centre(request):
    """Add a new cost centre with optional initial payment"""
    if request.method == 'POST':
        name = request.POST.get('name')
        received = request.POST.get('received', '').strip()
        
        if not name or not name.strip():
            messages.error(request, 'Cost Centre name is required')
            return redirect('finance')
        
        try:
            # Create cost centre with 0.00 initially
            cost_centre = CostCentre.objects.create(
                name=name.strip(),
                total_received=Decimal('0.00'),
                total_spent=Decimal('0.00')
            )
            
            # If initial amount provided, create a payment
            if received:
                try:
                    amount = Decimal(received)
                    if amount.as_tuple().exponent < -2:
                        messages.error(request, 'Amount must have at most 2 decimal places')
                        return redirect('finance')
                    
                    if amount > Decimal('0.00'):
                        from adminpanel.models import CostCentrePayment
                        CostCentrePayment.objects.create(
                            cost_centre=cost_centre,
                            amount=amount,
                            description='Initial amount'
                        )
                        messages.success(request, f'Cost Centre "{name}" created with initial payment of R {amount:.2f}')
                    else:
                        messages.success(request, f'Cost Centre "{name}" created (no initial payment)')
                except (InvalidOperation, ValueError, TypeError):
                    messages.error(request, 'Invalid amount format')
                    return redirect('finance')
            else:
                messages.success(request, f'Cost Centre "{name}" created successfully')
            
            return redirect('finance')
        except Exception as e:
            messages.error(request, f'Error creating cost centre: {str(e)}')
            return redirect('finance')
    
    return redirect('finance')
    
@login_required
def add_expenditure(request):
    if request.method == 'POST':
        cost_centre_id = request.POST.get('cost_centre_id')
        month = request.POST.get('month')
        name = request.POST.get('name')
        category = request.POST.get('category')

        # Safely convert numeric fields with validation
        try:
            amount_str = request.POST.get('amount', '0') or '0.00'
            amount = Decimal(amount_str)
            
            # Validate decimal places (max 2)
            if amount.as_tuple().exponent < -2:
                messages.error(request, 'Please enter a valid number with up to 2 decimal places')
                return redirect('finance')
            
            oracle_str = request.POST.get('oracle_balance', '0') or '0.00'
            oracle = Decimal(oracle_str)
            
            # Validate decimal places (max 2)
            if oracle.as_tuple().exponent < -2:
                messages.error(request, 'Please enter a valid oracle balance with up to 2 decimal places')
                return redirect('finance')
                
        except InvalidOperation:
            messages.error(request, 'Invalid number format: please enter a valid number')
            return redirect('finance')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid number format')
            return redirect('finance')

        try:
            with connection.cursor() as cursor:
                # Check if cost centre exists
                cursor.execute("""
                    SELECT id, total_spent FROM adminpanel_costcentre WHERE id = %s
                """, [cost_centre_id])
                cc_row = cursor.fetchone()
                
                if not cc_row:
                    messages.error(request, 'Cost Centre not found')
                    return redirect('finance')
                
                cc_id, total_spent = cc_row
                
                # Calculate opening balance for expenditure
                opening_balance = safe_decimal(total_spent, Decimal('0'))
                closing_balance = opening_balance - amount
                
                # Insert expenditure
                cursor.execute("""
                    INSERT INTO adminpanel_expenditure 
                    (cost_centre_id, month, name, category, amount, opening_balance, closing_balance, oracle_balance)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, [cost_centre_id, month, name, category, str(amount), str(opening_balance), str(closing_balance), str(oracle)])
                
                # Update cost centre total_spent
                new_total = opening_balance + amount
                cursor.execute("""
                    UPDATE adminpanel_costcentre 
                    SET total_spent = %s
                    WHERE id = %s
                """, [str(new_total), cost_centre_id])
                
                messages.success(request, 'Expenditure added successfully')
                return redirect('finance')
                
        except InvalidOperation:
            messages.error(request, 'Error processing numbers: invalid format')
            return redirect('finance')
        except Exception as e:
            messages.error(request, f'Error adding expenditure: {str(e)}')
            return redirect('finance')


@login_required
def get_expenditures(request, cost_centre_id):
    """Get expenditures for a cost centre using raw SQL"""
    try:
        data = []
        
        with connection.cursor() as cursor:
            # Check if cost centre exists
            cursor.execute("""
                SELECT id FROM adminpanel_costcentre WHERE id = %s
            """, [cost_centre_id])
            
            if not cursor.fetchone():
                return JsonResponse({'error': 'Cost centre not found'}, status=404)
            
            # Fetch expenditures
            cursor.execute("""
                SELECT id, month, name, category, amount, opening_balance, closing_balance, oracle_balance
                FROM adminpanel_expenditure
                WHERE cost_centre_id = %s
                ORDER BY id
            """, [cost_centre_id])
            
            for row in cursor.fetchall():
                exp_id, month, name, category, amount, opening_balance, closing_balance, oracle_balance = row
                
                # Convert to float safely
                try:
                    amount = float(amount) if amount else 0
                    opening_balance = float(opening_balance) if opening_balance else 0
                    closing_balance = float(closing_balance) if closing_balance else 0
                    oracle_balance = float(oracle_balance) if oracle_balance else 0
                except (ValueError, TypeError):
                    amount = opening_balance = closing_balance = oracle_balance = 0
                
                data.append({
                    'month': month,
                    'name': name,
                    'category': category,
                    'amount': str(amount),
                    'opening_balance': str(opening_balance),
                    'closing_balance': str(closing_balance),
                    'oracle_balance': str(oracle_balance),
                })
        
        return JsonResponse({'expenditures': data})
    except Exception as e:
        return JsonResponse({'error': f'Error fetching expenditures: {str(e)}'}, status=500)

@login_required
def delete_cost_centre(request, pk):
    """Delete a cost centre using raw SQL"""
    try:
        with connection.cursor() as cursor:
            # Check if cost centre exists
            cursor.execute("""
                SELECT id, name FROM adminpanel_costcentre WHERE id = %s
            """, [pk])
            row = cursor.fetchone()
            
            if not row:
                messages.error(request, 'Cost centre not found')
                return redirect('finance')
            
            cost_centre_id, cost_centre_name = row
            
            if request.method == 'POST':
                # Delete associated expenditures first
                cursor.execute("""
                    DELETE FROM adminpanel_expenditure WHERE cost_centre_id = %s
                """, [cost_centre_id])
                
                # Delete cost centre
                cursor.execute("""
                    DELETE FROM adminpanel_costcentre WHERE id = %s
                """, [cost_centre_id])
                
                messages.success(request, 'Cost centre deleted successfully')
                return redirect('finance')
            
            # For GET request, return a simple confirmation message
            return render(request, 'adminpanel/confirm_delete.html', {
                'cost_centre': {'id': cost_centre_id, 'name': cost_centre_name}
            })
    except Exception as e:
        messages.error(request, f'Error processing cost centre: {str(e)}')
        return redirect('finance')

@login_required
def edit_cost_centre(request, pk):
    """Edit a cost centre - now only allows name editing since total_received is calculated from payments"""
    try:
        cost_centre = CostCentre.objects.get(id=pk)
        
        if request.method == 'POST':
            name = request.POST.get('name', cost_centre.name)
            
            if not name or name.strip() == '':
                messages.error(request, 'Cost Centre name cannot be empty')
                return redirect('finance')
            
            try:
                cost_centre.name = name
                cost_centre.save(update_fields=['name'])
                messages.success(request, 'Cost Centre updated successfully')
            except Exception as e:
                messages.error(request, f'Error saving Cost Centre: {str(e)}')
            
            return redirect('finance')
        
        return redirect('finance')
    except CostCentre.DoesNotExist:
        messages.error(request, 'Cost Centre not found')
        return redirect('finance')
    except Exception as e:
        messages.error(request, f'Error processing cost centre: {str(e)}')
        return redirect('finance')

@login_required
def add_payment(request):
    """Add an incremental payment to a cost centre"""
    if request.method == 'POST':
        cost_centre_id = request.POST.get('cost_centre_id')
        amount_str = request.POST.get('amount')
        description = request.POST.get('description', '')
        
        if not cost_centre_id or not amount_str:
            messages.error(request, 'Cost Centre and Amount are required')
            return redirect('finance')
        
        try:
            cost_centre = CostCentre.objects.get(id=cost_centre_id)
            from adminpanel.models import CostCentrePayment
            
            # Validate and convert amount
            amount = Decimal(amount_str)
            if amount.as_tuple().exponent < -2:
                messages.error(request, 'Amount must have at most 2 decimal places')
                return redirect('finance')
            
            # Create payment
            CostCentrePayment.objects.create(
                cost_centre=cost_centre,
                amount=amount,
                description=description
            )
            
            messages.success(request, f'Payment of R {amount:.2f} added successfully')
        except CostCentre.DoesNotExist:
            messages.error(request, 'Cost Centre not found')
        except (InvalidOperation, ValueError, TypeError):
            messages.error(request, 'Invalid amount format')
        except Exception as e:
            messages.error(request, f'Error adding payment: {str(e)}')
        
        return redirect('finance')
    
    return redirect('finance')

@login_required
def delete_payment(request, payment_id):
    """Delete a payment from cost centre"""
    try:
        from adminpanel.models import CostCentrePayment
        payment = CostCentrePayment.objects.get(id=payment_id)
        cost_centre = payment.cost_centre
        payment.delete()
        
        # Recalculate total_received
        total = CostCentrePayment.objects.filter(cost_centre=cost_centre).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        cost_centre.total_received = Decimal(str(total))
        cost_centre.save(update_fields=['total_received'])
        
        messages.success(request, 'Payment deleted successfully')
    except Exception as e:
        messages.error(request, f'Error deleting payment: {str(e)}')
    
    return redirect('finance')

@login_required
def edit_expenditure(request, pk):
    """Edit an expenditure using raw SQL"""
    try:
        with connection.cursor() as cursor:
            # Fetch expenditure
            cursor.execute("""
                SELECT id, cost_centre_id, month, name, category, amount, opening_balance, oracle_balance
                FROM adminpanel_expenditure WHERE id = %s
            """, [pk])
            row = cursor.fetchone()
            
            if not row:
                messages.error(request, 'Expenditure not found')
                return redirect('finance')
            
            exp_id, cost_centre_id, old_month, old_name, old_category, old_amount, old_opening_balance, old_oracle_balance = row
            
            if request.method == 'POST':
                month = request.POST.get('month', old_month)
                name = request.POST.get('name', old_name)
                category = request.POST.get('category', old_category)
                
                # Validate and convert amount with error handling
                try:
                    amount_str = request.POST.get('amount', str(old_amount))
                    if not amount_str or amount_str.strip() == '':
                        amount_str = '0.00'
                    amount = Decimal(amount_str)
                    
                    # Validate decimal places (max 2)
                    if amount.as_tuple().exponent < -2:
                        messages.error(request, 'Please enter a valid number with up to 2 decimal places')
                        return redirect('finance')
                        
                except InvalidOperation:
                    messages.error(request, 'Invalid amount: please enter a valid number')
                    return redirect('finance')
                except (ValueError, TypeError):
                    messages.error(request, 'Invalid amount format')
                    return redirect('finance')
                
                # Validate and convert oracle_balance with error handling
                try:
                    oracle_str = request.POST.get('oracle_balance', str(old_oracle_balance))
                    if not oracle_str or oracle_str.strip() == '':
                        oracle_str = '0.00'
                    oracle_balance = Decimal(oracle_str)
                    
                    # Validate decimal places (max 2)
                    if oracle_balance.as_tuple().exponent < -2:
                        messages.error(request, 'Please enter a valid Oracle balance with up to 2 decimal places')
                        return redirect('finance')
                        
                except InvalidOperation:
                    messages.error(request, 'Invalid Oracle balance: please enter a valid number')
                    return redirect('finance')
                except (ValueError, TypeError):
                    messages.error(request, 'Invalid Oracle balance format')
                    return redirect('finance')
                
                try:
                    # Calculate closing balance
                    opening_balance = Decimal(str(old_opening_balance))
                    closing_balance = opening_balance - amount
                    
                    # Update expenditure
                    cursor.execute("""
                        UPDATE adminpanel_expenditure
                        SET month = %s, name = %s, category = %s, amount = %s, 
                            opening_balance = %s, closing_balance = %s, oracle_balance = %s
                        WHERE id = %s
                    """, [month, name, category, str(amount), str(opening_balance), str(closing_balance), str(oracle_balance), exp_id])
                    
                    messages.success(request, 'Expenditure updated successfully')
                except InvalidOperation:
                    messages.error(request, 'Error calculating balance: invalid number format')
                except Exception as e:
                    messages.error(request, f'Error saving Expenditure: {str(e)}')
                
                return redirect('finance')
            
            return redirect('finance')
    except Exception as e:
        messages.error(request, f'Error processing expenditure: {str(e)}')
        return redirect('finance')

@login_required
def delete_expenditure(request, pk):
    """Delete an expenditure using raw SQL"""
    try:
        with connection.cursor() as cursor:
            # Check if expenditure exists
            cursor.execute("""
                SELECT id FROM adminpanel_expenditure WHERE id = %s
            """, [pk])
            
            if not cursor.fetchone():
                messages.error(request, 'Expenditure not found')
                return redirect('finance')
            
            if request.method == 'POST':
                cursor.execute("""
                    DELETE FROM adminpanel_expenditure WHERE id = %s
                """, [pk])
                
                messages.success(request, 'Expenditure deleted successfully')
                return redirect('finance')
            
            return redirect('finance')
    except Exception as e:
        messages.error(request, f'Error deleting expenditure: {str(e)}')
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
                # Create SystemMedia record for feedback file
                MediaService.create_media_record(
                    file_obj=feedback.uploaded_file,
                    uploaded_by=request.user,
                    purpose='feedback',
                    description=f"Feedback for submission: {submission.title}",
                    related_object=submission
                )
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
@login_required
@user_passes_test(lambda u: u.role in ['admin', 'supervisor'])
def supervisor_dashboard(request):
    supervisor = request.user
    student_profiles = StudentProfile.objects.filter(supervisor=supervisor).select_related('user')

    # Use supervisor-only template if user is a supervisor (not admin)
    template = 'adminpanel/supervisor_only_dashboard.html' if request.user.role == 'supervisor' else 'adminpanel/supervisor_dashboard.html'
    
    return render(request, template, {
        'student_profiles': student_profiles
    })

@login_required
@login_required
@user_passes_test(lambda u: u.role in ['admin', 'supervisor'])
def student_detail_view(request, student_id):
    student_user = CustomUser.objects.get(id=student_id)
    student_profile = StudentProfile.objects.get(user=student_user)
    
    # Permission check: Only allow supervisors to view their own supervised students
    if student_profile.supervisor != request.user:
        from django.http import Http404
        raise Http404("You don't have permission to view this student's details.")
    
    submission_history = Submission.objects.filter(student=student_user)
    meeting_history = Meeting.objects.filter(student=student_user)
    # Get messages in conversation: messages from student to supervisor OR from supervisor to student
    from django.db.models import Q
    chat_messages = ChatMessage.objects.filter(
        Q(sender=student_user, recipient=request.user) |  # Student sent to supervisor
        Q(sender=request.user, recipient=student_user)     # Supervisor sent to student
    ).order_by('timestamp')
    form = SupervisorFeedbackForm()
    chat_form = ChatForm()

    return render(request, 'adminpanel/student_detail.html', {
        'student_user': student_user,
        'student_profile': student_profile,
        'submission_history': submission_history,
        'meeting_history': meeting_history,
        'form' : form,
        'chat_messages': chat_messages,
        'chat_form': chat_form,
        'user': request.user
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
    from manager.models import Book, Chapter
    
    # Fetch all books with their chapters
    books = Book.objects.prefetch_related('chapters').order_by('-created_at')
    
    # Convert to JSON-friendly format for template
    books_data = []
    for book in books:
        chapters = book.chapters.all().order_by('chapter_number')
        chapters_list = [{
            'id': ch.id,
            'number': ch.chapter_number,
            'title': ch.title,
            'author': ch.author,
            'editor': ch.editor or '',
            'status': ch.status,
            'lastUpdated': ch.last_updated.strftime('%Y-%m-%d %H:%M')
        } for ch in chapters]
        
        books_data.append({
            'id': book.id,
            'title': book.title,
            'status': book.status,
            'author': book.lead_author,
            'dueDate': book.due_date.strftime('%Y-%m-%d') if book.due_date else '',
            'chapters': {
                'total': book.total_chapters,
                'completed': book.completed_chapters,
                'list': chapters_list
            },
            'description': book.description or '',
            'publisher': book.publisher or ''
        })
    
    return render(request, 'adminpanel/admin_book.html', {
        'books_json': books_data,
        'book_status_choices': Book.STATUS_CHOICES,
    })


@csrf_exempt
@login_required
def update_book_status(request, book_id):
    """Update the status of a book via kanban drag-and-drop"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            
            book = get_object_or_404(Book, id=book_id)
            
            # Validate status is in allowed choices
            valid_statuses = [choice[0] for choice in Book.STATUS_CHOICES]
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
            
            # Update and save
            book.status = new_status
            book.save()
            return JsonResponse({'success': True})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

# def admin_required(view_func):
#     return user_passes_test(lambda u: u.is_authenticated and u.role == 'admin')(view_func)

def admin_required(view_func):
    return user_passes_test(
        lambda u: u.is_authenticated and u.role == 'admin'
        # login_url='/login/'  # This is breaking code. wierd custom login_url override.
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
