from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection

#Here  is the Default Django User_ROLE_VALIDATION.
from django.contrib.auth.decorators import login_required, user_passes_test

from users.models import CustomUser
from users.forms import CustomUserCreationForm
from manager.models import Book, Chapter
from .models import CostCentre, Expenditure, ResearchCentre, SupervisorProfile, SupervisorFeedback, Notification, AuditLog, ClockInRecord
from .audit_service import (
    log_cost_centre_creation, log_cost_centre_edit, log_cost_centre_deletion,
    log_expenditure_creation, log_expenditure_edit, log_expenditure_deletion,
    log_payment_creation, log_payment_deletion
)
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
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
from django.apps import apps
from projects.models import StudentProfile
import csv
from datetime import datetime, timedelta
import io
import os
import re
import zipfile
from xml.etree import ElementTree

from .media_models import SystemMedia
from .crm_logic import build_context as build_crm_logic_context


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


def optional_decimal(value):
    if value is None or str(value).strip() == '':
        return None
    return safe_decimal(value)


def normalize_header(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value or '').strip().lower()).strip('_')


def get_cell_text(cell, shared_strings):
    value = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
    if value is None:
        inline = cell.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is')
        text = inline.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t') if inline is not None else None
        return text.text if text is not None else ''

    raw_value = value.text or ''
    if cell.attrib.get('t') == 's':
        try:
            return shared_strings[int(raw_value)]
        except (IndexError, ValueError):
            return ''
    return raw_value


def xlsx_column_index(cell_ref):
    letters = re.sub(r'[^A-Z]', '', cell_ref.upper())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord('A') + 1)
    return index - 1


def read_xlsx_rows(file_obj):
    file_obj.seek(0)
    with zipfile.ZipFile(file_obj) as workbook:
        shared_strings = []
        if 'xl/sharedStrings.xml' in workbook.namelist():
            root = ElementTree.fromstring(workbook.read('xl/sharedStrings.xml'))
            for item in root.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                shared_strings.append(''.join(text.text or '' for text in item.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')))

        sheet_name = 'xl/worksheets/sheet1.xml'
        root = ElementTree.fromstring(workbook.read(sheet_name))
        rows = []
        for row in root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
            values = []
            for cell in row.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                index = xlsx_column_index(cell.attrib.get('r', 'A1'))
                while len(values) <= index:
                    values.append('')
                values[index] = get_cell_text(cell, shared_strings)
            rows.append(values)
        return rows


def parse_import_date(value):
    value = str(value or '').strip()
    if not value:
        return None
    if len(value) >= 10:
        parsed = parse_date(value[:10])
        if parsed:
            return parsed
    parsed = parse_date(value)
    if parsed:
        return parsed
    try:
        excel_epoch = datetime(1899, 12, 30).date()
        return excel_epoch + timedelta(days=int(float(value)))
    except (TypeError, ValueError):
        return None


def parse_import_decimal(value):
    value = str(value or '').strip()
    if not value:
        return None
    value = value.replace('R', '').replace(',', '').strip()
    return safe_decimal(value, None)


def xml_escape(value):
    return (
        str(value if value is not None else '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def cell_ref(row_number, column_number):
    letters = ''
    column_number += 1
    while column_number:
        column_number, remainder = divmod(column_number - 1, 26)
        letters = chr(65 + remainder) + letters
    return f'{letters}{row_number}'


def build_sheet_xml(rows):
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row):
            ref = cell_ref(row_index, column_index)
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{xml_escape(value)}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheetData>{"".join(xml_rows)}</sheetData>
</worksheet>'''


def create_xlsx_workbook(sheets):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
''' + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets) + 1)) + '''
</Types>''')
        workbook.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
        workbook.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>''' + ''.join(f'<sheet name="{xml_escape(name)[:31]}" sheetId="{i}" r:id="rId{i}"/>' for i, (name, _) in enumerate(sheets, start=1)) + '''</sheets>
</workbook>''')
        workbook.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
''' + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1)) + '''
</Relationships>''')
        for index, (_, rows) in enumerate(sheets, start=1):
            workbook.writestr(f'xl/worksheets/sheet{index}.xml', build_sheet_xml(rows))
    output.seek(0)
    return output.getvalue()


def xlsx_response(filename, sheets):
    response = HttpResponse(
        create_xlsx_workbook(sheets),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


READONLY_FINANCE_ROLES = ['dean', 'financialadmin']
FINANCE_EDITOR_ROLES = ['admin', 'centrehead']
ADMIN_VIEW_ROLES = ['admin', 'dean', 'centrehead']
COMMUNIQUE_ROLES = ['staff', 'manager', 'admin', 'dean', 'centrehead', 'financialadmin', 'student', 'supervisor']
CRM_ROLES = ['dean', 'centrehead']


def is_admin(user):
    return user.is_authenticated and user.role == 'admin'


def is_admin_or_dean(user):
    return user.is_authenticated and user.role in ADMIN_VIEW_ROLES


def can_view_admin_kanban(user):
    return user.is_authenticated and user.role in ADMIN_VIEW_ROLES


def can_edit_finance(user):
    return user.is_authenticated and user.role in FINANCE_EDITOR_ROLES


def can_view_crm(user):
    return user.is_authenticated and user.role in CRM_ROLES


def get_user_research_centre_id(user):
    return getattr(user, 'research_centre_id', None)


def get_accessible_cost_centre_ids(user):
    if getattr(user, 'role', None) != 'centrehead':
        return None
    research_centre_id = get_user_research_centre_id(user)
    if not research_centre_id:
        return []
    return list(CostCentre.objects.filter(research_centre_id=research_centre_id).values_list('id', flat=True))


def get_finance_redirect(user):
    return 'finance_readonly' if getattr(user, 'role', None) in READONLY_FINANCE_ROLES else 'finance'


def ensure_finance_editor(request, cost_centre=None):
    if not can_edit_finance(request.user):
        messages.error(request, "You do not have permission to change financial data.")
        return False

    if request.user.role == 'centrehead':
        research_centre_id = get_user_research_centre_id(request.user)
        if not research_centre_id:
            messages.error(request, "Your account is not assigned to a research centre.")
            return False
        if cost_centre is not None and cost_centre.research_centre_id != research_centre_id:
            messages.error(request, "You can only change data for your assigned research centre.")
            return False

    return True


@login_required
def admin_dashboard(request):
    return render(request, 'adminpanel/overview.html')

@login_required
def communique(request):
    if request.user.role not in COMMUNIQUE_ROLES:
        messages.error(request, "You do not have access to the Communique page.")
        return redirect('dashboard')

    template_uploads = SystemMedia.objects.filter(
        purpose='template',
        is_active=True,
        description__startswith='Communique template:'
    ).select_related('uploaded_by').order_by('-uploaded_at')

    return render(request, 'adminpanel/communique.html', {
        'template_uploads': template_uploads,
        'can_upload_templates': request.user.role == 'admin',
    })


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def upload_communique_template(request):
    template_name = request.POST.get('template_name', '').strip()
    template_file = request.FILES.get('template_file')

    if not template_name:
        messages.error(request, "Template name is required.")
        return redirect('communique')

    if not template_file:
        messages.error(request, "Please choose a template file.")
        return redirect('communique')

    allowed_extensions = {'.doc', '.docx', '.pdf'}
    extension = os.path.splitext(template_file.name.lower())[1]
    if extension not in allowed_extensions:
        messages.error(request, "Only Word documents and PDFs are supported.")
        return redirect('communique')

    MediaService.create_media_record_with_backup(
        file_obj=template_file,
        uploaded_by=request.user,
        purpose='template',
        description=f'Communique template: {template_name}',
        backup_to_db=True,
    )
    messages.success(request, f'Template "{template_name}" uploaded successfully.')
    return redirect('communique')


@login_required
def download_communique_template(request, media_id):
    media = get_object_or_404(
        SystemMedia,
        id=media_id,
        purpose='template',
        is_active=True,
        description__startswith='Communique template:',
    )

    content = media.file_blob
    if content is None and media.file:
        media.file.open('rb')
        content = media.file.read()
        media.file.close()

    if content is None:
        messages.error(request, "Template file is not available.")
        return redirect('communique')

    response = HttpResponse(content, content_type=media.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{media.filename}"'
    return response

@login_required
def app_kanban(request):
    phases = ["UX/UI", "Architecture", "Frontend", "Backend", "Testing", "Deployment"]
    return render(request, 'adminpanel/app_kanban.html', {'phases': phases})


@login_required
@user_passes_test(lambda u: u.role in ['admin', 'dean', 'manager'])
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
    if request.user.role == 'centrehead':
        users = users.filter(research_centre_id=request.user.research_centre_id)

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
        'recent_notifications': recent_notifications,
        'can_manage_overview': request.user.role == 'admin',
    })



@login_required
@user_passes_test(is_admin_or_dean)
def manage_users(request):
    search = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')

    users = CustomUser.objects.exclude(role='admin').select_related('research_centre')
    all_users = CustomUser.objects.exclude(role='admin').select_related('research_centre')  # All users for filter dropdown

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
        'all_users': all_users,
        'form': CustomUserCreationForm(),
        'edit_forms': edit_forms,
        'role_totals': role_totals,
        'role_counts': role_labels,
        'research_centres': ResearchCentre.objects.all(),
        'is_readonly_user_management': request.user.role == 'dean',
    })


@login_required
@user_passes_test(is_admin)
def create_user(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = form.cleaned_data['role']
            user.research_centre = form.cleaned_data.get('research_centre')
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
        research_centre_id = request.POST.get('research_centre')
        user.research_centre = ResearchCentre.objects.filter(id=research_centre_id).first() if research_centre_id else None

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

    if request.user.role in READONLY_FINANCE_ROLES:
        return redirect('finance_readonly')
    if not can_edit_finance(request.user):
        messages.error(request, "You do not have access to the finance dashboard.")
        return redirect('overview')

    scoped_cost_centre_ids = None
    if request.user.role == 'centrehead':
        scoped_cost_centre_ids = get_accessible_cost_centre_ids(request.user)
        if not scoped_cost_centre_ids:
            messages.error(request, "Your account is not assigned to a research centre with cost centres.")
            return redirect('communique')

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
            if scoped_cost_centre_ids is not None and cc_id not in scoped_cost_centre_ids:
                continue
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

        cursor.execute("""
            SELECT cc.id, cc.code, cc.name, cc.moa_amount, cc.research_centre_id, rc.name
            FROM adminpanel_costcentre cc
            LEFT JOIN adminpanel_researchcentre rc ON cc.research_centre_id = rc.id
            ORDER BY cc.name
        """)
        for cc_id, code, name, moa_amount, research_centre_id, research_centre_name in cursor.fetchall():
            if scoped_cost_centre_ids is not None and cc_id not in scoped_cost_centre_ids:
                continue
            cost_centres_map[cc_id] = {'id': cc_id, 'code': code, 'name': name, 'moa_amount': safe_decimal(moa_amount), 'research_centre_id': research_centre_id, 'research_centre_name': research_centre_name}

        cursor.execute("""
            SELECT id, cost_centre_id, month, name, category, amount, opening_balance, closing_balance, oracle_balance, expense_id
            FROM adminpanel_expenditure
            ORDER BY id DESC
        """)
        for exp_id, cc_id, month, name, category, amount, opening_balance, closing_balance, oracle_balance, expense_id in cursor.fetchall():
            if scoped_cost_centre_ids is not None and cc_id not in scoped_cost_centre_ids:
                continue
            amount_dec = safe_decimal(amount)
            opening_dec = safe_decimal(opening_balance)
            closing_dec = safe_decimal(closing_balance)
            oracle_dec = optional_decimal(oracle_balance)

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
                'oracle_balance': decimal_to_float(oracle_dec) if oracle_dec is not None else None,
                'expense_id': expense_id,
            })

    cost_centres = []
    for cc_id, info in cost_centres_map.items():
        total_received = payment_summary[cc_id]['total']
        total_spent = expenditure_summary[cc_id]
        total_remaining = total_received - total_spent
        moa_amount = info.get('moa_amount', Decimal('0.00'))
        moa_outstanding = moa_amount - total_received

        info.update({
            'total_received': decimal_to_float(total_received),
            'total_spent': decimal_to_float(total_spent),
            'total_remaining': decimal_to_float(total_remaining),
            'moa_amount': decimal_to_float(moa_amount),
            'moa_outstanding': decimal_to_float(moa_outstanding),
            'get_total_received': decimal_to_float(total_received),
            'payment_count': payment_summary[cc_id]['count']
        })
        cost_centres.append(info)

    category_totals_dict = {}
    monthly_totals_dict = {}
    for exp in all_expenditures:
        category = exp['category']
        category_totals_dict.setdefault(category, 0)
        category_totals_dict[category] += exp['amount']

        month = exp['month']
        monthly_totals_dict.setdefault(month, 0)
        monthly_totals_dict[month] += exp['amount']

    # Convert to list of dicts for template
    category_totals = [{'category': cat, 'total': total} for cat, total in sorted(category_totals_dict.items())]
    monthly_totals = [{'month': month, 'total': total} for month, total in sorted(monthly_totals_dict.items())]

    # Fetch audit logs (most recent first)
    audit_logs = AuditLog.objects.all().order_by('-timestamp')[:100]  # Get last 100 entries

    return render(request, 'adminpanel/finance.html', {
        'cost_centres': cost_centres,
        'all_expenditures': all_expenditures,
        'category_totals': category_totals,
        'monthly_totals': monthly_totals,
        'category_choices': Expenditure.EXPENSE_CATEGORY_CHOICES,
            'payments_by_cc': payments_by_cc,
            'audit_logs': audit_logs,
            'is_readonly': False,
            'can_add_cost_centre': request.user.role == 'admin',
            'can_edit_finance': True,
            'research_centres': ResearchCentre.objects.all(),
    })

@login_required
@user_passes_test(lambda u: u.role in ['admin', 'dean', 'financialadmin'])
def finance_readonly(request):
    """Read-only finance dashboard for financial admin users"""
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

        cursor.execute("""
            SELECT cc.id, cc.code, cc.name, cc.moa_amount, cc.research_centre_id, rc.name
            FROM adminpanel_costcentre cc
            LEFT JOIN adminpanel_researchcentre rc ON cc.research_centre_id = rc.id
            ORDER BY cc.name
        """)
        for cc_id, code, name, moa_amount, research_centre_id, research_centre_name in cursor.fetchall():
            cost_centres_map[cc_id] = {'id': cc_id, 'code': code, 'name': name, 'moa_amount': safe_decimal(moa_amount), 'research_centre_id': research_centre_id, 'research_centre_name': research_centre_name}

        cursor.execute("""
            SELECT id, cost_centre_id, month, name, category, amount, opening_balance, oracle_balance, expense_id
            FROM adminpanel_expenditure
            ORDER BY month DESC
        """)
        for exp_id, cc_id, month, name, category, amount, opening_balance, oracle_balance, expense_id in cursor.fetchall():
            amount_dec = safe_decimal(amount)
            opening_balance_dec = safe_decimal(opening_balance)
            oracle_dec = optional_decimal(oracle_balance)
            cc_info = cost_centres_map.get(cc_id, {'id': cc_id, 'name': f'CC {cc_id}', 'moa_amount': Decimal('0')})
            expenditure_summary[cc_id] += amount_dec

            all_expenditures.append({
                'id': exp_id,
                'cost_centre_id': cc_id,
                'cost_centre': cc_info,
                'cost_centre_name': cc_info['name'],
                'month': month,
                'name': name,
                'category': category,
                'amount': decimal_to_float(amount_dec),
                'opening_balance': decimal_to_float(opening_balance_dec),
                'oracle_balance': decimal_to_float(oracle_dec) if oracle_dec is not None else None,
                'expense_id': expense_id,
            })

    cost_centres = []
    for cc_id, cc_info in cost_centres_map.items():
        summary = payment_summary[cc_id]
        total_spent = expenditure_summary[cc_id]
        total_remaining = cc_info['moa_amount'] - total_spent
        moa_outstanding = cc_info['moa_amount'] - summary['total']

        cost_centres.append({
            'id': cc_id,
            'code': cc_info.get('code', ''),
            'name': cc_info['name'],
            'research_centre_id': cc_info.get('research_centre_id'),
            'research_centre_name': cc_info.get('research_centre_name'),
            'payment_count': summary['count'],
            'total_received': decimal_to_float(summary['total']),
            'get_total_received': decimal_to_float(summary['total']),
            'total_spent': decimal_to_float(total_spent),
            'total_remaining': decimal_to_float(total_remaining),
            'moa_amount': decimal_to_float(cc_info['moa_amount']),
            'moa_outstanding': decimal_to_float(moa_outstanding),
        })

    cost_centres.sort(key=lambda x: x['name'])

    category_totals_dict = {}
    monthly_totals_dict = {}
    for exp in all_expenditures:
        category = exp['category']
        category_totals_dict.setdefault(category, 0)
        category_totals_dict[category] += exp['amount']

        month = exp['month']
        monthly_totals_dict.setdefault(month, 0)
        monthly_totals_dict[month] += exp['amount']

    category_totals = [{'category': cat, 'total': total} for cat, total in sorted(category_totals_dict.items())]
    monthly_totals = [{'month': month, 'total': total} for month, total in sorted(monthly_totals_dict.items())]

    audit_logs = AuditLog.objects.all().order_by('-timestamp')[:100]

    return render(request, 'adminpanel/finance.html', {
        'cost_centres': cost_centres,
        'all_expenditures': all_expenditures,
        'category_totals': category_totals,
        'monthly_totals': monthly_totals,
        'category_choices': Expenditure.EXPENSE_CATEGORY_CHOICES,
        'payments_by_cc': payments_by_cc,
        'audit_logs': audit_logs,
        'is_readonly': True,
        'can_add_cost_centre': False,
        'can_edit_finance': False,
        'research_centres': ResearchCentre.objects.all(),
    })


def get_finance_scope_queryset(user):
    queryset = CostCentre.objects.select_related('research_centre').all().order_by('name')
    if getattr(user, 'role', None) == 'centrehead':
        queryset = queryset.filter(research_centre_id=get_user_research_centre_id(user))
    return queryset


@login_required
def download_expense_import_template(request):
    if not can_edit_finance(request.user):
        messages.error(request, "You do not have permission to import expenses.")
        return redirect(get_finance_redirect(request.user))

    sample_cost_centre = get_finance_scope_queryset(request.user).first()
    cost_centre_name = sample_cost_centre.name if sample_cost_centre else 'Exact Cost Centre Name'
    rows = [
        ['expense_id', 'cost_centre', 'date_from', 'date_to', 'name', 'category', 'amount', 'oracle_balance'],
        ['EXP-2026-0001', cost_centre_name, '2026-05-01', '2026-05-31', 'Example Person or Supplier', 'Invoices', '1500.00', '1500.00'],
    ]
    return xlsx_response('expense_upload_template.xlsx', [('Expense Upload', rows)])


@login_required
def download_finance_summary_excel(request):
    if request.user.role not in ['admin', 'centrehead', 'dean', 'financialadmin']:
        messages.error(request, "You do not have permission to download finance data.")
        return redirect('overview')

    cost_centres = get_finance_scope_queryset(request.user)
    cost_centre_ids = list(cost_centres.values_list('id', flat=True))
    expenditures = Expenditure.objects.select_related('cost_centre', 'cost_centre__research_centre').filter(cost_centre_id__in=cost_centre_ids).order_by('cost_centre__name', 'month', 'id')
    CostCentrePayment = apps.get_model('adminpanel', 'CostCentrePayment')
    payments = CostCentrePayment.objects.select_related('cost_centre').filter(cost_centre_id__in=cost_centre_ids).order_by('cost_centre__name', '-payment_date')

    summary_rows = [[
        'cost_centre_code', 'cost_centre_name', 'research_centre', 'moa_amount',
        'total_received', 'total_spent', 'total_remaining', 'moa_outstanding'
    ]]
    for cost_centre in cost_centres:
        total_received = cost_centre.get_total_received()
        total_spent = expenditures.filter(cost_centre=cost_centre).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        moa_amount = safe_decimal(cost_centre.moa_amount)
        summary_rows.append([
            cost_centre.code,
            cost_centre.name,
            cost_centre.research_centre.name if cost_centre.research_centre else '',
            moa_amount,
            total_received,
            total_spent,
            total_received - total_spent,
            moa_amount - total_received,
        ])

    expense_rows = [[
        'expense_id', 'database_id', 'cost_centre', 'month', 'date_from', 'date_to',
        'name', 'category', 'amount', 'opening_balance', 'closing_balance', 'oracle_balance', 'oracle_check'
    ]]
    for expenditure in expenditures:
        oracle_check = ''
        if expenditure.oracle_balance is None:
            oracle_check = 'Pending'
        elif safe_decimal(expenditure.oracle_balance) == safe_decimal(expenditure.amount):
            oracle_check = 'Matched'
        else:
            oracle_check = 'Review'
        expense_rows.append([
            expenditure.expense_id or '',
            expenditure.id,
            expenditure.cost_centre.name,
            expenditure.month or '',
            expenditure.date_from or '',
            expenditure.date_to or '',
            expenditure.name,
            expenditure.category,
            expenditure.amount,
            expenditure.opening_balance,
            expenditure.closing_balance,
            expenditure.oracle_balance if expenditure.oracle_balance is not None else '',
            oracle_check,
        ])

    payment_rows = [['cost_centre', 'payment_date', 'amount', 'description']]
    for payment in payments:
        payment_rows.append([payment.cost_centre.name, payment.payment_date, payment.amount, payment.description or ''])

    return xlsx_response(
        'finance_summary.xlsx',
        [('Overall Summary', summary_rows), ('Expenses', expense_rows), ('Payments', payment_rows)]
    )


@login_required
@require_http_methods(["POST"])
def upload_expense_excel(request):
    if not ensure_finance_editor(request):
        return redirect(get_finance_redirect(request.user))

    upload = request.FILES.get('expense_file')
    if not upload:
        messages.error(request, "Please choose an Excel file to upload.")
        return redirect('finance')

    if not upload.name.lower().endswith('.xlsx'):
        messages.error(request, "Please upload an .xlsx file using the template.")
        return redirect('finance')

    try:
        rows = read_xlsx_rows(upload)
    except Exception as exc:
        messages.error(request, f"Could not read Excel file: {exc}")
        return redirect('finance')

    if not rows:
        messages.error(request, "The uploaded Excel file is empty.")
        return redirect('finance')

    headers = [normalize_header(header) for header in rows[0]]
    required_headers = {'expense_id', 'cost_centre', 'date_from', 'date_to', 'name', 'category', 'amount'}
    missing_headers = required_headers - set(headers)
    if missing_headers:
        messages.error(request, f"Excel missing required columns: {', '.join(sorted(missing_headers))}")
        return redirect('finance')

    category_values = {choice[0] for choice in Expenditure.EXPENSE_CATEGORY_CHOICES}
    scoped_cost_centres = get_finance_scope_queryset(request.user)
    cost_centres_by_name = {cc.name.strip().lower(): cc for cc in scoped_cost_centres}
    cost_centres_by_code = {cc.code.strip().lower(): cc for cc in scoped_cost_centres if cc.code}
    existing_expense_ids = set(Expenditure.objects.exclude(expense_id__isnull=True).exclude(expense_id='').values_list('expense_id', flat=True))

    created_count = 0
    skipped_count = 0
    errors = []

    for index, row in enumerate(rows[1:], start=2):
        values = {headers[col_index]: (row[col_index] if col_index < len(row) else '') for col_index in range(len(headers))}
        if not any(str(value).strip() for value in values.values()):
            continue

        expense_id = str(values.get('expense_id', '')).strip()
        cost_centre_key = str(values.get('cost_centre', '')).strip()
        name = str(values.get('name', '')).strip()
        category = str(values.get('category', '')).strip()
        amount = parse_import_decimal(values.get('amount'))
        oracle_balance = parse_import_decimal(values.get('oracle_balance'))
        date_from = parse_import_date(values.get('date_from'))
        date_to = parse_import_date(values.get('date_to'))

        if not expense_id:
            errors.append(f"Row {index}: Expense ID is required to prevent duplicates.")
            continue
        if expense_id in existing_expense_ids:
            skipped_count += 1
            continue

        cost_centre = cost_centres_by_name.get(cost_centre_key.lower()) or cost_centres_by_code.get(cost_centre_key.lower())
        if not cost_centre:
            errors.append(f"Row {index}: record failed because cost_centre name mismatch: '{cost_centre_key}'.")
            continue
        if not name:
            errors.append(f"Row {index}: Name is required.")
            continue
        if category not in category_values:
            errors.append(f"Row {index}: Invalid category '{category}'.")
            continue
        if amount is None:
            errors.append(f"Row {index}: Invalid amount.")
            continue
        if not date_from or not date_to:
            errors.append(f"Row {index}: date_from and date_to must be valid dates.")
            continue

        opening_balance = Expenditure.objects.filter(cost_centre=cost_centre).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        expenditure = Expenditure.objects.create(
            expense_id=expense_id,
            cost_centre=cost_centre,
            month=date_from.strftime('%Y-%m'),
            date_from=date_from,
            date_to=date_to,
            name=name,
            category=category,
            amount=amount,
            opening_balance=opening_balance,
            oracle_balance=oracle_balance,
        )
        existing_expense_ids.add(expense_id)
        log_expenditure_creation(expenditure, request.user)
        created_count += 1

    if created_count:
        messages.success(request, f"Uploaded {created_count} expense record(s).")
    if skipped_count:
        messages.info(request, f"Skipped {skipped_count} duplicate expense ID record(s).")
    for error in errors[:8]:
        messages.error(request, error)
    if len(errors) > 8:
        messages.error(request, f"{len(errors) - 8} more row error(s) were not shown.")
    if not created_count and not skipped_count and not errors:
        messages.info(request, "No expense rows were found in the upload.")

    return redirect('finance')

@login_required
@login_required
def add_cost_centre(request):
    """Add a new cost centre with optional initial payment and MOA amount"""
    if request.user.role != 'admin':
        messages.error(request, "Only admins can add cost centres.")
        return redirect(get_finance_redirect(request.user))

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        name = request.POST.get('name')
        research_centre_id = request.POST.get('research_centre')
        received = request.POST.get('received', '').strip()
        moa_amount = request.POST.get('moa_amount', '').strip()
        
        if not name or not name.strip():
            messages.error(request, 'Cost Centre name is required')
            return redirect('finance')
        existing_client = CostCentre.objects.select_related('research_centre').filter(name__iexact=name.strip()).first()
        if existing_client:
            centre_name = existing_client.research_centre.name if existing_client.research_centre else 'Unassigned centre'
            messages.error(request, f'Client already associated with {centre_name}. No duplicate client/cost centre was created.')
            return redirect('finance')
        
        try:
            # Create cost centre with 0.00 initially
            moa = Decimal(moa_amount) if moa_amount else Decimal('0.00')
            
            # Check if code already exists
            if code and CostCentre.objects.filter(code=code).exists():
                existing_by_code = CostCentre.objects.select_related('research_centre').filter(code=code).first()
                centre_name = existing_by_code.research_centre.name if existing_by_code and existing_by_code.research_centre else 'Unassigned centre'
                messages.error(request, f'Client already associated with {centre_name} under cost centre code "{code}".')
                return redirect('finance')
            
            cost_centre = CostCentre.objects.create(
                code=code,
                name=name.strip(),
                research_centre=ResearchCentre.objects.filter(id=research_centre_id).first() if research_centre_id else None,
                total_received=Decimal('0.00'),
                total_spent=Decimal('0.00'),
                moa_amount=moa
            )
            
            # Log the cost centre creation
            log_cost_centre_creation(cost_centre, request.user)
            
            # If initial amount provided, create a payment
            if received:
                try:
                    amount = Decimal(received)
                    if amount.as_tuple().exponent < -2:
                        messages.error(request, 'Amount must have at most 2 decimal places')
                        return redirect('finance')
                    
                    if amount > Decimal('0.00'):
                        from adminpanel.models import CostCentrePayment
                        payment = CostCentrePayment.objects.create(
                            cost_centre=cost_centre,
                            amount=amount,
                            description='Initial amount'
                        )
                        # Log the payment creation
                        log_payment_creation(payment, request.user)
                        if moa > Decimal('0.00'):
                            messages.success(request, f'Cost Centre "{name}" created successfully! Initial payment: R {amount:.2f}, MOA Amount: R {moa:.2f}')
                        else:
                            messages.success(request, f'Cost Centre "{name}" created with initial payment of R {amount:.2f}')
                    else:
                        if moa > Decimal('0.00'):
                            messages.success(request, f'Cost Centre "{name}" created successfully with MOA Amount: R {moa:.2f}')
                        else:
                            messages.success(request, f'Cost Centre "{name}" created (no initial payment)')
                except (InvalidOperation, ValueError, TypeError):
                    messages.error(request, 'Invalid amount format')
                    return redirect('finance')
            else:
                if moa > Decimal('0.00'):
                    messages.success(request, f'Cost Centre "{name}" created successfully with MOA Amount: R {moa:.2f}')
                else:
                    messages.success(request, f'Cost Centre "{name}" created successfully')
            
            return redirect('finance')
        except Exception as e:
            messages.error(request, f'Error creating cost centre: {str(e)}')
            return redirect('finance')
    
    return redirect('finance')
    
@login_required
def add_expenditure(request):
    if not ensure_finance_editor(request):
        return redirect(get_finance_redirect(request.user))

    if request.method == 'POST':
        cost_centre_id = request.POST.get('cost_centre_id')
        date_from_str = request.POST.get('date_from')
        date_to_str = request.POST.get('date_to')
        name = request.POST.get('name')
        category = request.POST.get('category')
        oracle_balance = optional_decimal(request.POST.get('oracle_balance'))
        expense_id = request.POST.get('expense_id', '').strip() or None

        # Safely convert amount with validation
        try:
            amount_str = request.POST.get('amount', '0') or '0.00'
            amount = Decimal(amount_str)
            
            # Validate decimal places (max 2)
            if amount.as_tuple().exponent < -2:
                messages.error(request, 'Please enter a valid number with up to 2 decimal places')
                return redirect('finance')
                
        except InvalidOperation:
            messages.error(request, 'Invalid number format: please enter a valid number')
            return redirect('finance')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid number format')
            return redirect('finance')

        try:
            # Get cost centre
            cost_centre = get_object_or_404(CostCentre, id=cost_centre_id)
            if not ensure_finance_editor(request, cost_centre):
                return redirect(get_finance_redirect(request.user))
            if expense_id and Expenditure.objects.filter(expense_id=expense_id).exists():
                messages.error(request, f'Expense ID "{expense_id}" already exists. Use a unique ID to prevent duplicates.')
                return redirect('finance')
            
            # Parse date range
            date_from = None
            date_to = None
            month = None
            
            if date_from_str:
                date_from = parse_date(date_from_str)
                month = date_from.strftime('%Y-%m')
            if date_to_str:
                date_to = parse_date(date_to_str)
            
            # Calculate balances from current total_spent
            total_spent = safe_decimal(cost_centre.total_spent, Decimal('0'))
            opening_balance = total_spent
            closing_balance = opening_balance - amount
            
            # Create expenditure
            expenditure = Expenditure.objects.create(
                cost_centre=cost_centre,
                month=month,
                name=name,
                category=category,
                amount=amount,
                opening_balance=opening_balance,
                closing_balance=closing_balance,
                oracle_balance=oracle_balance,
                expense_id=expense_id,
                date_from=date_from,
                date_to=date_to
            )
            
            # Update cost centre total_spent
            cost_centre.total_spent = closing_balance
            cost_centre.save()
            
            # Log the creation
            log_expenditure_creation(expenditure, request.user)
            
            messages.success(request, 'Expenditure added successfully')
            return redirect('finance')
                
        except Exception as e:
            messages.error(request, f'Error adding expenditure: {str(e)}')
            return redirect('finance')


@login_required
def get_expenditures(request, cost_centre_id):
    """Get expenditures for a cost centre using raw SQL"""
    try:
        cost_centre = get_object_or_404(CostCentre, id=cost_centre_id)
        if request.user.role == 'centrehead' and cost_centre.research_centre_id != get_user_research_centre_id(request.user):
            return JsonResponse({'error': 'You can only view expenditures for your assigned research centre'}, status=403)

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
                SELECT id, month, name, category, amount, opening_balance, closing_balance, oracle_balance, expense_id
                FROM adminpanel_expenditure
                WHERE cost_centre_id = %s
                ORDER BY id
            """, [cost_centre_id])
            
            for row in cursor.fetchall():
                exp_id, month, name, category, amount, opening_balance, closing_balance, oracle_balance, expense_id = row
                
                # Convert to float safely
                try:
                    amount = float(amount) if amount else 0
                    opening_balance = float(opening_balance) if opening_balance else 0
                    closing_balance = float(closing_balance) if closing_balance else 0
                    oracle_balance = float(oracle_balance) if oracle_balance is not None else None
                except (ValueError, TypeError):
                    amount = opening_balance = closing_balance = 0
                    oracle_balance = None
                
                data.append({
                    'id': exp_id,
                    'cost_centre_id': cost_centre_id,
                    'cost_centre_name': cost_centre.name,
                    'month': month,
                    'name': name,
                    'category': category,
                    'amount': str(amount),
                    'opening_balance': str(opening_balance),
                    'closing_balance': str(closing_balance),
                    'oracle_balance': str(oracle_balance) if oracle_balance is not None else None,
                    'expense_id': expense_id,
                })
        
        return JsonResponse({'expenditures': data})
    except Exception as e:
        return JsonResponse({'error': f'Error fetching expenditures: {str(e)}'}, status=500)

@login_required
def delete_cost_centre(request, pk):
    """Delete a cost centre using raw SQL"""
    if request.user.role != 'admin':
        messages.error(request, "Only admins can delete cost centres.")
        return redirect(get_finance_redirect(request.user))

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
                # Log the deletion
                log_cost_centre_deletion(cost_centre_id, cost_centre_name, request.user)
                
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
    """Edit a cost centre - allows name and MOA amount editing"""
    if request.user.role != 'admin':
        messages.error(request, "Only admins can edit cost centres.")
        return redirect(get_finance_redirect(request.user))

    try:
        cost_centre = CostCentre.objects.get(id=pk)
        
        if request.method == 'POST':
            name = request.POST.get('name', cost_centre.name)
            research_centre_id = request.POST.get('research_centre')
            moa_amount = request.POST.get('moa_amount', '').strip()
            
            if not name or name.strip() == '':
                messages.error(request, 'Cost Centre name cannot be empty')
                return redirect('finance')
            
            try:
                # Store previous values for audit log
                previous_values = {
                    'name': cost_centre.name,
                    'moa_amount': str(cost_centre.moa_amount)
                }
                
                cost_centre.name = name
                cost_centre.research_centre = ResearchCentre.objects.filter(id=research_centre_id).first() if research_centre_id else None
                if moa_amount:
                    cost_centre.moa_amount = Decimal(moa_amount)
                cost_centre.save()
                
                # Log the edit
                log_cost_centre_edit(cost_centre, request.user, previous_values)
                
                messages.success(request, 'Cost Centre updated successfully')
            except (InvalidOperation, ValueError, TypeError):
                messages.error(request, 'Invalid MOA amount format')
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
    if not ensure_finance_editor(request):
        return redirect(get_finance_redirect(request.user))

    if request.method == 'POST':
        cost_centre_id = request.POST.get('cost_centre_id')
        amount_str = request.POST.get('amount')
        description = request.POST.get('description', '')
        
        if not cost_centre_id or not amount_str:
            messages.error(request, 'Cost Centre and Amount are required')
            return redirect('finance')
        
        try:
            cost_centre = CostCentre.objects.get(id=cost_centre_id)
            if not ensure_finance_editor(request, cost_centre):
                return redirect(get_finance_redirect(request.user))
            from adminpanel.models import CostCentrePayment
            
            # Validate and convert amount
            amount = Decimal(amount_str)
            if amount.as_tuple().exponent < -2:
                messages.error(request, 'Amount must have at most 2 decimal places')
                return redirect('finance')
            
            # Create payment
            payment = CostCentrePayment.objects.create(
                cost_centre=cost_centre,
                amount=amount,
                description=description
            )
            
            # Log the payment creation
            log_payment_creation(payment, request.user)
            
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
    if not ensure_finance_editor(request):
        return redirect(get_finance_redirect(request.user))

    try:
        from adminpanel.models import CostCentrePayment
        payment = CostCentrePayment.objects.get(id=payment_id)
        cost_centre = payment.cost_centre
        if not ensure_finance_editor(request, cost_centre):
            return redirect(get_finance_redirect(request.user))
        payment_description = f"{cost_centre.name} - R {payment.amount}"
        
        payment.delete()
        
        # Log the payment deletion
        log_payment_deletion(payment_id, payment_description, request.user)
        
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
    if not ensure_finance_editor(request):
        return redirect(get_finance_redirect(request.user))

    try:
        with connection.cursor() as cursor:
            # Fetch expenditure
            cursor.execute("""
                SELECT id, cost_centre_id, month, name, category, amount, opening_balance, oracle_balance, expense_id
                FROM adminpanel_expenditure WHERE id = %s
            """, [pk])
            row = cursor.fetchone()
            
            if not row:
                messages.error(request, 'Expenditure not found')
                return redirect('finance')
            
            exp_id, cost_centre_id, old_month, old_name, old_category, old_amount, old_opening_balance, old_oracle_balance, old_expense_id = row
            if request.user.role == 'centrehead' and cost_centre_id not in get_accessible_cost_centre_ids(request.user):
                messages.error(request, "You can only edit expenditures for your assigned research centre.")
                return redirect('finance')
            
            if request.method == 'POST':
                month = request.POST.get('month', old_month)
                name = request.POST.get('name', old_name)
                category = request.POST.get('category', old_category)
                expense_id_value = request.POST.get('expense_id', '').strip() or None
                if expense_id_value and Expenditure.objects.filter(expense_id=expense_id_value).exclude(id=exp_id).exists():
                    messages.error(request, f'Expense ID "{expense_id_value}" already exists.')
                    return redirect('finance')
                
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
                    oracle_balance = optional_decimal(request.POST.get('oracle_balance', old_oracle_balance))
                    
                    # Validate decimal places (max 2)
                    if oracle_balance is not None and oracle_balance.as_tuple().exponent < -2:
                        messages.error(request, 'Please enter a valid Oracle balance with up to 2 decimal places')
                        return redirect('finance')
                        
                except InvalidOperation:
                    messages.error(request, 'Invalid Oracle balance: please enter a valid number')
                    return redirect('finance')
                except (ValueError, TypeError):
                    messages.error(request, 'Invalid Oracle balance format')
                    return redirect('finance')
                
                try:
                    # Store previous values for audit log
                    previous_values = {
                        'month': old_month,
                        'name': old_name,
                        'category': old_category,
                        'amount': str(old_amount),
                        'oracle_balance': str(old_oracle_balance) if old_oracle_balance is not None else None,
                        'expense_id': old_expense_id,
                    }
                    
                    # Calculate closing balance
                    opening_balance = Decimal(str(old_opening_balance))
                    closing_balance = opening_balance - amount
                    
                    # Update expenditure
                    cursor.execute("""
                        UPDATE adminpanel_expenditure
                        SET month = %s, name = %s, category = %s, amount = %s, 
                            opening_balance = %s, closing_balance = %s, oracle_balance = %s, expense_id = %s
                        WHERE id = %s
                    """, [month, name, category, str(amount), str(opening_balance), str(closing_balance), str(oracle_balance) if oracle_balance is not None else None, expense_id_value, exp_id])
                    
                    # Get the updated expenditure for audit logging
                    expenditure = Expenditure.objects.get(id=pk)
                    log_expenditure_edit(expenditure, request.user, previous_values)
                    
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
    if not ensure_finance_editor(request):
        return redirect(get_finance_redirect(request.user))

    try:
        with connection.cursor() as cursor:
            # Fetch expenditure details before deletion
            cursor.execute("""
                SELECT id, cost_centre_id, name, category, month FROM adminpanel_expenditure WHERE id = %s
            """, [pk])
            
            row = cursor.fetchone()
            if not row:
                messages.error(request, 'Expenditure not found')
                return redirect('finance')
            
            exp_id, cost_centre_id, exp_name, exp_category, exp_month = row
            if request.user.role == 'centrehead' and cost_centre_id not in get_accessible_cost_centre_ids(request.user):
                messages.error(request, "You can only delete expenditures for your assigned research centre.")
                return redirect('finance')
            
            if request.method == 'POST':
                # Log the deletion with expenditure details
                expenditure_name = f"{exp_name} ({exp_category}) - {exp_month}"
                log_expenditure_deletion(exp_id, expenditure_name, request.user)
                
                cursor.execute("""
                    DELETE FROM adminpanel_expenditure WHERE id = %s
                """, [pk])
                
                messages.success(request, 'Expenditure deleted successfully')
                return redirect('finance')
            
            return redirect('finance')
    except Exception as e:
        messages.error(request, f'Error deleting expenditure: {str(e)}')
        return redirect('finance')


# ===========================
# BUDGET FORECAST VIEWS
# ===========================

@login_required
@login_required
def add_budget_forecast(request):
    """Add a new budget forecast"""
    if not ensure_finance_editor(request):
        return redirect(get_finance_redirect(request.user))

    if request.method == 'POST':
        print("\n=== BUDGET FORECAST RECEIVED ===")
        print(f"POST data: {request.POST}")
        
        cost_centre_id = request.POST.get('cost_centre_id')
        date_from_str = request.POST.get('date_from')
        date_to_str = request.POST.get('date_to')
        name = request.POST.get('name')
        category = request.POST.get('category')
        amount_str = request.POST.get('amount')
        
        # Pad dates with "-01" if missing day (yyyy-MM format → yyyy-MM-01)
        if date_from_str and len(date_from_str) == 7:
            date_from_str = date_from_str + '-01'
            print(f"Padded date_from: {date_from_str}")
        if date_to_str and len(date_to_str) == 7:
            date_to_str = date_to_str + '-01'
            print(f"Padded date_to: {date_to_str}")
        
        print(f"cost_centre_id: {cost_centre_id}")
        print(f"date_from: {date_from_str}")
        print(f"date_to: {date_to_str}")
        print(f"name: {name}")
        print(f"category: {category}")
        print(f"amount: {amount_str}")

        try:
            amount_str = amount_str or '0.00'
            amount = Decimal(amount_str)
            
            if amount.as_tuple().exponent < -2:
                messages.error(request, 'Please enter a valid number with up to 2 decimal places')
                return redirect('finance')
                
        except (InvalidOperation, ValueError, TypeError) as e:
            print(f"ERROR parsing amount: {e}")
            messages.error(request, 'Invalid number format')
            return redirect('finance')

        try:
            # Validate cost centre
            if not cost_centre_id:
                print("ERROR: No cost centre ID provided")
                messages.error(request, 'Please select a cost centre')
                return redirect('finance')
            
            # Try to fetch cost centre - handle decimal conversion errors
            try:
                cost_centre = CostCentre.objects.get(id=cost_centre_id)
                if not ensure_finance_editor(request, cost_centre):
                    return redirect(get_finance_redirect(request.user))
                print(f"✅ Cost centre found: {cost_centre.name}")
            except Exception as e:
                print(f"⚠️ Error fetching cost centre via ORM: {e}")
                # Fallback: fetch using raw SQL to bypass decimal issues
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("SELECT id, name, research_centre_id FROM adminpanel_costcentre WHERE id = %s", [cost_centre_id])
                    row = cursor.fetchone()
                    if row:
                        # Create a temporary object with just id and name
                        cost_centre = CostCentre(id=row[0], name=row[1])
                        cost_centre.research_centre_id = row[2]
                        if not ensure_finance_editor(request, cost_centre):
                            return redirect(get_finance_redirect(request.user))
                        print(f"✅ Cost centre found (via raw SQL): {cost_centre.name}")
                    else:
                        print(f"ERROR: Cost centre {cost_centre_id} not found")
                        messages.error(request, 'Cost centre not found')
                        return redirect('finance')
            
            # Parse dates
            date_from = None
            date_to = None
            if date_from_str:
                date_from = parse_date(date_from_str)
                print(f"✅ Parsed date_from: {date_from}")
            if date_to_str:
                date_to = parse_date(date_to_str)
                print(f"✅ Parsed date_to: {date_to}")
            
            # Extract month from date_from
            month = None
            if date_from:
                month = date_from.strftime('%Y-%m-%d')
                print(f"✅ Month set to: {month}")
            
            # Create budget forecast (not released yet)
            BudgetForecast = apps.get_model('adminpanel', 'BudgetForecast')
            forecast = BudgetForecast.objects.create(
                cost_centre=cost_centre,
                month=month,
                date_from=date_from,
                date_to=date_to,
                name=name,
                category=category,
                amount=amount,
                is_released=False
            )
            
            print(f"✅ SUCCESS: Forecast created with ID {forecast.id}")
            print("=== END FORECAST DATA ===\n")
            messages.success(request, 'Budget forecast added successfully')
            return redirect('finance')
                
        except Exception as e:
            import traceback
            print(f"❌ ERROR creating forecast: {e}")
            traceback.print_exc()
            print("=== END FORECAST DATA ===\n")
            messages.error(request, f'Error adding forecast: {str(e)}')
            return redirect('finance')
    
    return redirect('finance')


@login_required
def get_budget_forecasts(request, cost_centre_id):
    """Get budget forecasts for a cost centre as JSON"""
    try:
        cost_centre = get_object_or_404(CostCentre, id=cost_centre_id)
        if request.user.role == 'centrehead' and cost_centre.research_centre_id != get_user_research_centre_id(request.user):
            return JsonResponse({'error': 'You can only view forecasts for your assigned research centre'}, status=403)

        BudgetForecast = apps.get_model('adminpanel', 'BudgetForecast')
        forecasts = BudgetForecast.objects.filter(
            cost_centre_id=cost_centre_id,
            is_released=False
        ).values(
            'id', 'month', 'name', 'category', 'amount', 'date_from', 'date_to', 'created_at', 'cost_centre_id'
        )
        
        data = []
        for forecast in forecasts:
            # Calculate months
            if forecast['date_from'] and forecast['date_to']:
                date_from = forecast['date_from']
                date_to = forecast['date_to']
                days_diff = (date_to - date_from).days
                months = max(1, round(days_diff / 30))
            else:
                months = 1
            
            total_cost = float(forecast['amount']) * months
            
            data.append({
                'id': forecast['id'],
                'month': forecast['month'],
                'name': forecast['name'],
                'category': forecast['category'],
                'amount': float(forecast['amount']),
                'date_from': str(forecast['date_from']) if forecast['date_from'] else None,
                'date_to': str(forecast['date_to']) if forecast['date_to'] else None,
                'months': months,
                'total_cost': total_cost,
                'cost_centre_id': forecast['cost_centre_id']
            })
        
        return JsonResponse({'forecasts': data}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def edit_budget_forecast(request, pk):
    if not ensure_finance_editor(request):
        return JsonResponse({'error': 'You do not have permission to change financial data'}, status=403)

    try:
        BudgetForecast = apps.get_model('adminpanel', 'BudgetForecast')
        forecast = get_object_or_404(BudgetForecast, id=pk, is_released=False)
        if not ensure_finance_editor(request, forecast.cost_centre):
            return JsonResponse({'error': 'You can only edit forecasts for your assigned research centre'}, status=403)

        body = json.loads(request.body) if request.body else request.POST
        name = body.get('name', '').strip()
        category = body.get('category', '').strip()
        amount = optional_decimal(body.get('amount'))
        date_from = parse_date(body.get('date_from')) if body.get('date_from') else None
        date_to = parse_date(body.get('date_to')) if body.get('date_to') else None

        if not name or not category or amount is None:
            return JsonResponse({'error': 'Name, category, and amount are required'}, status=400)

        forecast.name = name
        forecast.category = category
        forecast.amount = amount
        forecast.date_from = date_from
        forecast.date_to = date_to
        forecast.month = date_from.strftime('%Y-%m-%d') if date_from else None
        forecast.save()

        return JsonResponse({'success': True, 'message': 'Forecast updated successfully'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_budget_forecast(request, pk):
    """Delete a budget forecast"""
    if not ensure_finance_editor(request):
        return redirect(get_finance_redirect(request.user))

    try:
        BudgetForecast = apps.get_model('adminpanel', 'BudgetForecast')
        forecast = get_object_or_404(BudgetForecast, id=pk)
        if not ensure_finance_editor(request, forecast.cost_centre):
            return redirect(get_finance_redirect(request.user))
        forecast.delete()
        messages.success(request, 'Budget forecast deleted successfully')
        return redirect('finance')
    except Exception as e:
        messages.error(request, f'Error deleting forecast: {str(e)}')
        return redirect('finance')


@login_required
@require_http_methods(["POST"])
def release_budget_forecasts(request, cost_centre_id):
    """Release budget forecasts to Monthly Expenditure Tracker - supports both all and selected"""
    if not ensure_finance_editor(request):
        return JsonResponse({'error': 'You do not have permission to change financial data'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    try:
        import json
        body = json.loads(request.body) if request.body else {}
        forecast_ids = body.get('forecast_ids', [])
        
        cost_centre = get_object_or_404(CostCentre, id=cost_centre_id)
        if not ensure_finance_editor(request, cost_centre):
            return JsonResponse({'error': 'You can only release forecasts for your assigned cost centre'}, status=403)
        BudgetForecast = apps.get_model('adminpanel', 'BudgetForecast')
        Expenditure = apps.get_model('adminpanel', 'Expenditure')
        
        # If no specific IDs provided, release all unreleased forecasts
        if not forecast_ids:
            forecasts = BudgetForecast.objects.filter(
                cost_centre=cost_centre,
                is_released=False
            )
        else:
            forecasts = BudgetForecast.objects.filter(
                id__in=forecast_ids,
                cost_centre=cost_centre,
                is_released=False
            )
        
        forecasts_list = list(forecasts)
        forecast_count = len(forecasts_list)
        
        with connection.cursor() as cursor:
            for forecast in forecasts_list:
                # Get current balance
                cursor.execute("""
                    SELECT total_spent FROM adminpanel_costcentre WHERE id = %s
                """, [cost_centre_id])
                cc_row = cursor.fetchone()
                current_spent = safe_decimal(cc_row[0] if cc_row else 0, Decimal('0'))
                
                # Calculate closing balance
                opening_balance = current_spent
                closing_balance = opening_balance - forecast.amount
                
                # Insert into expenditure
                cursor.execute("""
                    INSERT INTO adminpanel_expenditure 
                    (cost_centre_id, month, name, category, amount, opening_balance, closing_balance, oracle_balance, date_from, date_to)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    cost_centre_id,
                    forecast.month,
                    forecast.name,
                    forecast.category,
                    str(forecast.amount),
                    str(opening_balance),
                    str(closing_balance),
                    None,
                    forecast.date_from,
                    forecast.date_to
                ])
                
                # Update cost centre total_spent
                new_total = opening_balance + forecast.amount
                cursor.execute("""
                    UPDATE adminpanel_costcentre 
                    SET total_spent = %s
                    WHERE id = %s
                """, [str(new_total), cost_centre_id])
                
                # Mark forecast as released
                forecast.is_released = True
                forecast.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Released {forecast_count} forecast(s) to Monthly Expenditure Tracker'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def update_expenditure(request, pk):
    """Update an expenditure record"""
    if not ensure_finance_editor(request):
        return JsonResponse({'error': 'You do not have permission to change financial data'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    try:
        import json
        body = json.loads(request.body)
        name = body.get('name')
        amount = body.get('amount')
        oracle_balance = body.get('oracle_balance')
        
        Expenditure = apps.get_model('adminpanel', 'Expenditure')
        expenditure = get_object_or_404(Expenditure, id=pk)
        if not ensure_finance_editor(request, expenditure.cost_centre):
            return JsonResponse({'error': 'You can only update expenditures for your assigned cost centre'}, status=403)
        
        # Update fields
        if name:
            expenditure.name = name
        if amount:
            expenditure.amount = Decimal(amount)
        if oracle_balance is not None:
            expenditure.oracle_balance = optional_decimal(oracle_balance)
        
        expenditure.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Expenditure updated successfully'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def admin_kanban(request):
    return render(request, 'adminpanel/admin_kanban.html')


def get_crm_selected_centre(request):
    if request.user.role == 'centrehead':
        return ResearchCentre.objects.filter(id=get_user_research_centre_id(request.user)).first()

    centre_id = request.GET.get('centre')
    if centre_id:
        return ResearchCentre.objects.filter(id=centre_id).first()
    return None


def get_crm_scope(request):
    selected_centre = get_crm_selected_centre(request)
    centres = ResearchCentre.objects.all().order_by('name')
    if request.user.role == 'centrehead':
        centres = centres.filter(id=get_user_research_centre_id(request.user))

    cost_centres = CostCentre.objects.select_related('research_centre').all().order_by('name')
    users = CustomUser.objects.select_related('research_centre').filter(is_active=True).order_by('first_name', 'last_name', 'username')
    projects = Project.objects.select_related('assigned_user', 'created_by').prefetch_related('tasks', 'assignments__team_member__user').all().order_by('-created_at')

    if selected_centre:
        cost_centres = cost_centres.filter(research_centre=selected_centre)
        users = users.filter(research_centre=selected_centre)
        projects = projects.filter(
            Q(assigned_user__research_centre=selected_centre) |
            Q(created_by__research_centre=selected_centre) |
            Q(assignments__team_member__user__research_centre=selected_centre)
        ).distinct()

    return {
        'selected_centre': selected_centre,
        'research_centres': centres,
        'cost_centres': cost_centres,
        'users': users,
        'projects': projects,
    }


def project_progress(project):
    tasks = list(project.tasks.all())
    if not tasks:
        return 0
    return int(sum(task.progress for task in tasks) / len(tasks))


def project_centre_name(project):
    if project.assigned_user and project.assigned_user.research_centre:
        return project.assigned_user.research_centre.name
    if project.created_by and project.created_by.research_centre:
        return project.created_by.research_centre.name
    assignment = project.assignments.first()
    if assignment and assignment.team_member.user.research_centre:
        return assignment.team_member.user.research_centre.name
    return 'Unassigned'


def build_crm_context(request, active_tab):
    scope = get_crm_scope(request)
    cost_centres = list(scope['cost_centres'])
    users = list(scope['users'])
    projects = list(scope['projects'])
    today = timezone.now().date()

    total_revenue = Decimal('0.00')
    total_spent = Decimal('0.00')
    clients = []
    for cost_centre in cost_centres:
        received = cost_centre.get_total_received()
        spent = Expenditure.objects.filter(cost_centre=cost_centre).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_revenue += received
        total_spent += spent
        clients.append({
            'id': cost_centre.id,
            'code': cost_centre.code,
            'name': cost_centre.name,
            'sector': cost_centre.research_centre.name if cost_centre.research_centre else 'Unassigned',
            'ownership': cost_centre.research_centre.name if cost_centre.research_centre else 'Institutional',
            'lead': next((user for user in users if user.role == 'centrehead' and user.research_centre_id == cost_centre.research_centre_id), None),
            'total_received': received,
            'total_spent': spent,
            'estimated_profit': received - spent,
            'pipeline_value': safe_decimal(cost_centre.moa_amount) - received,
            'visibility': 'Institutional' if request.user.role == 'dean' else 'Centre',
        })

    engagements = []
    for project in projects:
        tasks = list(project.tasks.all())
        latest_task = max((task.created_at for task in tasks), default=project.created_at)
        progress = project_progress(project)
        stage = 'Active'
        if project.status == 'planning':
            stage = 'Prospect'
        elif project.status == 'on-hold':
            stage = 'On hold'
        elif project.status == 'completed':
            stage = 'Completed'

        engagements.append({
            'id': project.id,
            'name': project.name,
            'client': project_centre_name(project),
            'stage': stage,
            'status': project.status,
            'lead': project.assigned_user or project.created_by,
            'due_date': project.due_date,
            'last_contact': latest_task,
            'progress': progress,
            'team_count': project.assignments.count(),
            'visibility': 'Institutional',
            'is_overdue': bool(project.due_date and project.due_date < today and project.status != 'completed'),
        })

    centres = []
    for centre in scope['research_centres']:
        centre_users = [user for user in users if user.research_centre_id == centre.id]
        centre_costs = [client for client in clients if client['sector'] == centre.name]
        centre_projects = [engagement for engagement in engagements if engagement['client'] == centre.name]
        revenue = sum((client['total_received'] for client in centre_costs), Decimal('0.00'))
        spent = sum((client['total_spent'] for client in centre_costs), Decimal('0.00'))
        centres.append({
            'id': centre.id,
            'name': centre.name,
            'director': next((user for user in centre_users if user.role == 'centrehead'), None),
            'staff_count': len(centre_users),
            'client_count': len(centre_costs),
            'engagement_count': len(centre_projects),
            'revenue': revenue,
            'estimated_profit': revenue - spent,
            'avg_progress': int(sum(item['progress'] for item in centre_projects) / len(centre_projects)) if centre_projects else 0,
        })

    duplicate_clients = defaultdict(list)
    for client in clients:
        duplicate_clients[client['name'].lower()].append(client)

    oracle_mismatches = Expenditure.objects.select_related('cost_centre').filter(
        cost_centre__in=cost_centres,
        oracle_balance__isnull=False,
    ).exclude(oracle_balance=models.F('amount'))

    alerts = []
    for engagement in engagements:
        if engagement['is_overdue']:
            alerts.append({'level': 'High', 'type': 'Deadline', 'message': f"{engagement['name']} is past its due date.", 'owner': engagement['lead']})
        if engagement['last_contact'] and (timezone.now() - engagement['last_contact']).days > 60 and engagement['status'] != 'completed':
            alerts.append({'level': 'Medium', 'type': 'Contact Risk', 'message': f"{engagement['name']} has no recent activity in 60+ days.", 'owner': engagement['lead']})

    for cost_centre in cost_centres:
        if cost_centre.get_total_received() <= 0:
            alerts.append({'level': 'Medium', 'type': 'Payment', 'message': f"{cost_centre.name} has no recorded payments.", 'owner': None})

    for expenditure in oracle_mismatches[:20]:
        alerts.append({'level': 'High', 'type': 'Oracle', 'message': f"{expenditure.cost_centre.name}: Oracle balance differs for {expenditure.name}.", 'owner': None})

    for duplicates in duplicate_clients.values():
        centre_names = {client['sector'] for client in duplicates}
        if len(duplicates) > 1 and len(centre_names) > 1:
            alerts.append({'level': 'Medium', 'type': 'Overlap', 'message': f"{duplicates[0]['name']} appears across multiple centres.", 'owner': None})

    role_counts = Counter(user.role for user in users)
    active_engagements = [item for item in engagements if item['status'] in ['planning', 'in-progress']]

    context = {
        **scope,
        'active_tab': active_tab,
        'crm_tabs': [
            ('clients', 'Clients', 'bi-building'),
            ('centres', 'Centres', 'bi-diagram-3'),
            ('engagements', 'Engagements', 'bi-kanban'),
            ('directory', 'Directory', 'bi-journal-text'),
            ('financials', 'Financials', 'bi-cash-stack'),
            ('alerts', 'Alerts', 'bi-exclamation-triangle'),
        ],
        'clients': clients,
        'centres': centres,
        'engagements': engagements,
        'directory_engagements': [item for item in engagements if item['visibility'] != 'Private'],
        'alerts': alerts,
        'staff_directory': users,
        'role_counts': role_counts,
        'total_revenue': total_revenue,
        'total_spent': total_spent,
        'pipeline_value': sum((client['pipeline_value'] for client in clients), Decimal('0.00')),
        'estimated_profit': total_revenue - total_spent,
        'active_engagement_count': len(active_engagements),
        'client_count': len(clients),
    }
    return context


@login_required
@user_passes_test(can_view_crm)
def crm(request, tab='clients'):
    valid_tabs = {'clients', 'centres', 'engagements', 'directory', 'financials', 'alerts', 'reports'}
    if tab not in valid_tabs:
        tab = 'clients'
    return render(request, 'adminpanel/crm/crm.html', build_crm_logic_context(request, tab))


@login_required
@user_passes_test(can_view_crm)
def crm_reporting_data(request):
    context = build_crm_logic_context(request, 'reports')
    return JsonResponse({
        'success': True,
        'charts': context['crm_chart_data'],
        'metrics': {
            'clients': context['client_count'],
            'active_engagements': context['active_engagement_count'],
            'revenue': float(context['total_revenue']),
            'pipeline': float(context['pipeline_value']),
            'estimated_profit': float(context['estimated_profit']),
        },
    })


@login_required
@user_passes_test(can_view_crm)
def crm_report_export(request, period='annual'):
    if period not in ['annual', 'weekly']:
        period = 'annual'
    context = build_crm_logic_context(request, 'reports')
    now = timezone.now()
    title = 'Annual CRM Report' if period == 'annual' else 'Weekly CRM Report'
    html = render(request, 'adminpanel/crm/reports/system_report.doc.html', {
        **context,
        'report_title': title,
        'report_period': period.title(),
        'generated_at': now,
    }).content
    response = HttpResponse(html, content_type='application/msword')
    response['Content-Disposition'] = f'attachment; filename="crm_{period}_report_{now:%Y%m%d}.doc"'
    return response

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
    from manager.models import PaperStatusHistory
    
    internal_papers = Paper.objects.filter(internal_external='internal').order_by('-updated_at')
    external_papers = Paper.objects.filter(internal_external='external').order_by('-updated_at')
    
    # Add available statuses for the UI
    for paper in list(internal_papers) + list(external_papers):
        paper.available_statuses = paper.get_available_statuses()
    
    return render(request, 'adminpanel/admin_journal.html', {
        'internal_papers': internal_papers,
        'external_papers': external_papers,
        'internal_statuses': Paper.INTERNAL_STATUSES,
        'external_statuses': Paper.EXTERNAL_STATUSES,
    })


@login_required
def move_paper_external(request, paper_id):
    """Move a paper from internal to external with submission details"""
    from manager.models import PaperStatusHistory
    
    paper = get_object_or_404(Paper, id=paper_id)
    
    if request.method == 'POST':
        # Change type to external
        paper.internal_external = 'external'
        old_status = paper.status
        paper.status = 'submitted'
        paper.submission_date = request.POST.get('submission_date')
        paper.target_journal = request.POST.get('target_journal')
        paper.save()
        
        # Log status change
        PaperStatusHistory.objects.create(
            paper=paper,
            old_status=old_status,
            new_status='submitted',
            changed_by=request.user,
            reason=f'Moved to external - Target: {paper.target_journal}'
        )
        
        messages.success(request, f"Paper '{paper.title}' moved to external (submitted to {paper.target_journal}).")
        return redirect('admin_journal')
    
    # GET - show form
    return render(request, 'adminpanel/move_paper_external.html', {'paper': paper})


@login_required
def return_paper_internal(request, paper_id):
    """Return a paper from external to internal with feedback"""
    from manager.models import PaperStatusHistory
    
    paper = get_object_or_404(Paper, id=paper_id)
    
    if request.method == 'POST':
        # Change type back to internal
        paper.internal_external = 'internal'
        old_status = paper.status
        paper.status = 'returned-feedback'
        paper.feedback_text = request.POST.get('feedback')
        paper.decision_date = request.POST.get('decision_date')
        paper.save()
        
        # Log status change
        PaperStatusHistory.objects.create(
            paper=paper,
            old_status=old_status,
            new_status='returned-feedback',
            changed_by=request.user,
            reason='Returned to internal with feedback'
        )
        
        messages.success(request, f"Paper '{paper.title}' returned to internal with feedback.")
        return redirect('admin_journal')
    
    # GET - show form
    return render(request, 'adminpanel/return_paper_internal.html', {'paper': paper})

@login_required
def admin_conferences(request):
    from manager.models import Conference
    
    internal_conferences = Conference.objects.filter(internal_external='internal').order_by('-updated_at')
    external_conferences = Conference.objects.filter(internal_external='external').order_by('-updated_at')
    
    return render(request, 'adminpanel/conferences.html', {
        'internal_conferences': internal_conferences,
        'external_conferences': external_conferences,
    })

@login_required
def add_conference(request):
    from manager.models import Conference
    
    if request.method == 'POST':
        conference = Conference(
            title=request.POST.get('conferenceTitle'),
            conference_name=request.POST.get('conferenceName'),
            location=request.POST.get('conferenceLocation'),
            lead_author=request.POST.get('leadAuthor'),
            co_authors=request.POST.get('coAuthors'),
            status=request.POST.get('conferenceStatus'),
            abstract=request.POST.get('conferenceAbstract'),
            submission_date=request.POST.get('submissionDate') or None,
            conference_date=request.POST.get('conferenceDate') or None,
            internal_external=request.POST.get('conferenceType'),
            created_by=request.user
        )
        
        if request.FILES.get('conferenceFile'):
            conference.paper = request.FILES['conferenceFile']
        
        conference.save()
        messages.success(request, 'Conference added successfully!')
        return redirect('admin_conferences')
    
    return render(request, 'adminpanel/conferences.html')

@login_required
def edit_conference(request, conference_id):
    """Handle conference edit via Django form with validation"""
    from manager.models import Conference
    from manager.forms import ConferenceForm
    from django.http import JsonResponse
    
    try:
        conference = get_object_or_404(Conference, id=conference_id)
        
        # Capture old M2M values before form processing
        old_co_authors = set(conference.co_authors_users.values_list('id', flat=True))
        old_reviewers = set(conference.assigned_reviewers.values_list('id', flat=True))
        
        # Use ConferenceForm for proper validation and handling of all field types
        form = ConferenceForm(request.POST, request.FILES, instance=conference)
        
        if form.is_valid():
            # Set the changed_by user for signal processing
            conference._changed_by = request.user
            
            # Capture new M2M values after form processes them
            new_co_authors = set(form.cleaned_data.get('co_authors_users', []).values_list('id', flat=True))
            new_reviewers = set(form.cleaned_data.get('assigned_reviewers', []).values_list('id', flat=True))
            
            # Set M2M change flags
            if old_co_authors != new_co_authors:
                conference._co_authors_changed = {
                    'old': list(conference.co_authors_users.all()),
                    'new': list(form.cleaned_data.get('co_authors_users', []))
                }
            
            if old_reviewers != new_reviewers:
                conference._reviewers_changed = {
                    'old': list(conference.assigned_reviewers.all()),
                    'new': list(form.cleaned_data.get('assigned_reviewers', []))
                }
            
            # Form.save() automatically handles all field types including ForeignKey and M2M
            form.save()
            return JsonResponse({'success': True, 'message': 'Conference updated successfully'})
        else:
            # Return form errors as JSON
            errors = {field: error[0] for field, error in form.errors.items()}
            return JsonResponse({
                'success': False,
                'errors': errors,
                'message': 'Form validation failed'
            }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
def delete_conference(request, conference_id):
    from manager.models import Conference
    
    try:
        conference = Conference.objects.get(id=conference_id)
        conference.delete()
        messages.success(request, 'Conference deleted successfully!')
    except Conference.DoesNotExist:
        messages.error(request, 'Conference not found.')
    
    return redirect('admin_conferences')

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
        can_view_admin_kanban
        # login_url='/login/'  # This is breaking code. wierd custom login_url override.
    )(view_func)

@admin_required
def admin_user_kanban(request, user_id):
    user = get_object_or_404(get_user_model(), id=user_id)
    if request.user.role == 'centrehead' and user.research_centre_id != request.user.research_centre_id:
        return HttpResponseBadRequest("You can only view task boards for users in your research centre.")

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


@login_required
@user_passes_test(lambda u: u.role == 'admin')
@csrf_exempt
def user_activity_api(request):
    """API endpoint for user activity data (clock-in, tasks, etc.)"""
    from datetime import datetime, timedelta
    
    employee_id = request.GET.get('employee_id', '')
    date_range = request.GET.get('date_range', '30')
    view_type = request.GET.get('view_type', 'overview')
    
    # Calculate date range
    today = timezone.now().date()
    if date_range == 'all':
        start_date = None
    else:
        days = int(date_range) if date_range.isdigit() else 30
        start_date = today - timedelta(days=days)
    
    # DEBUG: Log filter parameters
    print(f"\n🔍 [user_activity_api] Filtering:")
    print(f"   Today: {today}")
    print(f"   Date range: {date_range} days")
    print(f"   Start date: {start_date}")
    print(f"   Employee ID: {employee_id or 'All'}")
    
    # Filter clock records
    clock_records = ClockInRecord.objects.all()
    print(f"   Total records before filter: {clock_records.count()}")
    
    if employee_id:
        clock_records = clock_records.filter(employee_id=employee_id)
    if start_date:
        clock_records = clock_records.filter(clock_in_time__date__gte=start_date)
    
    filtered_count = clock_records.count()
    print(f"   Records after date filter: {filtered_count}")
    
    clock_records = clock_records.order_by('-clock_in_time')[:100]
    print(f"   Records for processing: {len(clock_records)} (limited to 100)")
    
    # Calculate metrics
    total_hours = Decimal('0.00')
    days_present = set()
    hours_by_date = {}
    day_distribution = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 'Friday': 0, 'Saturday': 0, 'Sunday': 0}
    
    for record in clock_records:
        if record.clock_out_time:
            duration = record.clock_out_time - record.clock_in_time
            hours = duration.total_seconds() / 3600
            total_hours += Decimal(str(hours))
            
            date_key = timezone.localtime(record.clock_in_time).strftime('%Y-%m-%d')
            hours_by_date[date_key] = hours_by_date.get(date_key, 0) + hours
            
            date_obj = timezone.localtime(record.clock_in_time).date()
            days_present.add(date_obj)
            
            day_name = timezone.localtime(record.clock_in_time).strftime('%A')
            day_distribution[day_name] += 1
    
    days_present_count = len(days_present)
    avg_daily_hours = float(total_hours) / max(days_present_count, 1) if days_present_count > 0 else 0
    
    # Get task progress
    tasks = Task.objects.all()
    if employee_id:
        tasks = tasks.filter(assigned_to_id=employee_id)
    
    if start_date:
        tasks = tasks.filter(created_at__date__gte=start_date)
    
    task_progress = []
    active_tasks_count = 0
    
    for task in tasks[:10]:  # Limit to 10 tasks
        progress = task.progress_percentage if hasattr(task, 'progress_percentage') else 0
        status = 'completed' if progress == 100 else ('in_progress' if progress > 0 else 'pending')
        
        if status in ['in_progress', 'pending']:
            active_tasks_count += 1
        
        task_progress.append({
            'name': task.title[:30],
            'progress': progress,
            'status': status,
            'start_day': 0,
            'duration': 5
        })
    
    # Weekly summary
    weekly_summary = []
    week_start = today - timedelta(days=today.weekday())
    
    for week_offset in range(4):
        current_week_start = week_start - timedelta(weeks=week_offset)
        current_week_end = current_week_start + timedelta(days=6)
        
        week_records = [r for r in clock_records if current_week_start <= timezone.localtime(r.clock_in_time).date() <= current_week_end]
        
        week_hours = Decimal('0.00')
        week_days = set()
        
        for record in week_records:
            if record.clock_out_time:
                duration = record.clock_out_time - record.clock_in_time
                week_hours += Decimal(str(duration.total_seconds() / 3600))
                week_days.add(timezone.localtime(record.clock_in_time).date())
        
        week_number = current_week_start.isocalendar()[1]
        avg_week_hours = float(week_hours) / max(len(week_days), 1) if len(week_days) > 0 else 0
        
        weekly_summary.append({
            'week_number': week_number,
            'date_range': f"{current_week_start.strftime('%b %d')} - {current_week_end.strftime('%b %d')}",
            'days_worked': len(week_days),
            'total_hours': float(week_hours),
            'avg_daily_hours': avg_week_hours
        })
    
    # Recent records for display
    recent_records = []
    for record in clock_records[:20]:
        recent_records.append({
            'date': timezone.localtime(record.clock_in_time).strftime('%Y-%m-%d'),
            'employee': record.employee.get_full_name() or record.employee.username,
            'clock_in': timezone.localtime(record.clock_in_time).strftime('%H:%M:%S'),
            'clock_out': timezone.localtime(record.clock_out_time).strftime('%H:%M:%S') if record.clock_out_time else '--',
            'duration': record.duration_display,
            'status': record.status
        })
    
    # Heatmap data (hours by day and hour)
    heatmap_data = {
        'Monday': [0] * 24,
        'Tuesday': [0] * 24,
        'Wednesday': [0] * 24,
        'Thursday': [0] * 24,
        'Friday': [0] * 24
    }
    
    for record in clock_records:
        if record.clock_out_time:
            day_name = timezone.localtime(record.clock_in_time).strftime('%A')
            hour = timezone.localtime(record.clock_in_time).hour
            
            if day_name in heatmap_data:
                duration = (record.clock_out_time - record.clock_in_time).total_seconds() / 3600
                heatmap_data[day_name][hour] += duration
    
    # Prepare response
    response_data = {
        'avg_daily_hours': avg_daily_hours,
        'total_hours': float(total_hours),
        'days_present': days_present_count,
        'active_tasks': active_tasks_count,
        'hours_by_date': [{'date': date, 'hours': hours} for date, hours in sorted(hours_by_date.items())],
        'day_distribution': day_distribution,
        'task_progress': task_progress,
        'weekly_summary': weekly_summary,
        'recent_records': recent_records,
        'heatmap_data': heatmap_data
    }
    
    return JsonResponse(response_data)


@login_required
def get_conference_form_html(request, conference_id):
    """Return the rendered Django form HTML for editing a conference"""
    try:
        from manager.models import Conference
        from manager.forms import ConferenceForm
        
        conference = get_object_or_404(Conference, id=conference_id)
        form = ConferenceForm(instance=conference)
        
        from django.template.loader import render_to_string
        html = render_to_string('includes/conference_form.html', {'form': form})
        
        return JsonResponse({
            'success': True,
            'form_html': html
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_conference_data(request, conference_id):
    """Return conference data as JSON for populating the edit form"""
    try:
        from manager.models import Conference
        
        conference = get_object_or_404(Conference, id=conference_id)
        
        # Serialize co_authors_users and assigned_reviewers IDs
        co_authors_ids = list(conference.co_authors_users.values_list('id', flat=True))
        reviewers_ids = list(conference.assigned_reviewers.values_list('id', flat=True))
        
        data = {
            'id': conference.id,
            'title': conference.title,
            'conference_name': conference.conference_name,
            'location': conference.location or '',
            'internal_external': conference.internal_external,
            'status': conference.status,
            'lead_author': conference.lead_author,
            'co_authors': conference.co_authors or '',
            'lead_author_user': conference.lead_author_user_id,
            'co_authors_users': co_authors_ids,
            'assigned_reviewers': reviewers_ids,
            'abstract': conference.abstract or '',
            'submission_date': conference.submission_date.isoformat() if conference.submission_date else '',
            'conference_date': conference.conference_date.isoformat() if conference.conference_date else '',
            'decision_date': conference.decision_date.isoformat() if conference.decision_date else '',
        }
        
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


# ============================================================================
# SCHEDULER TEST VIEW (NO LOGIN REQUIRED - FOR TESTING ONLY)
# ============================================================================

def test_scheduler_view(request):
    """Test view for availability auto-scheduler (no login required)"""
    from adminpanel.scheduler import get_team_availability_realtime
    
    team_data = get_team_availability_realtime()
    
    context = {
        'team_members': team_data,
        'total_members': len(team_data),
        'timestamp': timezone.now().isoformat(),
    }
    
    return render(request, 'adminpanel/test_scheduler.html', context)


@require_http_methods(["GET"])
def api_realtime_availability(request):
    """API endpoint for real-time availability (no login required for testing)"""
    from adminpanel.scheduler import get_team_availability_realtime
    
    try:
        team_data = get_team_availability_realtime()
        return JsonResponse({
            'success': True,
            'data': team_data,
            'timestamp': timezone.now().isoformat(),
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)
