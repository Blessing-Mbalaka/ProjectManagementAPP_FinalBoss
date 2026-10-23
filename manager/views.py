# views.py in manager app
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import models, transaction
from projects.models import Project, Task, Assignment,TeamMember
from projects.forms import ProjectForm, AssignmentForm, TaskForm
from .models import LearningContent, Template, Paper, Book, Chapter, PaperComment
from .forms import BookForm, PaperForm, EngagementLogForm
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import now
import json
from adminpanel.media_service import MediaService
from users.models import CustomUser
from django.contrib.auth import get_user_model
from collections import defaultdict
from django.db.models import Q
import pandas as pd
from django.core.files.base import ContentFile
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.shortcuts import render
from adminpanel.models import CostCentre, EngagementLog, FinancialProject, Notification
from adminpanel.notification_service import visible_notifications_for
from projects.scope import scope_books_for_user, scope_chapters_for_user, scope_outputs_for_user, scope_projects_for_user
from projects.work_scope import assigned_projects_for, can_update_task, manageable_projects_for, workable_tasks_for
from users.roles import can_manage_client_engagements, can_manage_projects, can_manage_publications, has_role
from projects.assignment_notifications import notify_project_assignment
from manager.publication_projects import sync_publication_project
from projects.workbook_import.application import WorkbookImportError, apply_workbook_preview
from projects.workbook_import.tokens import PreviewTokenError, sign_preview, unsign_preview
from projects.workbook_import.validation import validate_workbook
from projects.workbook_import.workbook import XLSX_MIME, build_template_workbook, read_workbook

User = get_user_model()

PROJECT_WORKBOOK_ROLES = {'manager', 'centrehead', 'dean', 'admin', 'financialadmin'}


def _can_use_project_workbooks(user):
    return bool(user.is_active and has_role(user, *PROJECT_WORKBOOK_ROLES))


@login_required
def download_project_workbook(request):
    if not _can_use_project_workbooks(request.user):
        return HttpResponseForbidden('You are not authorized to import project workbooks.')
    response = HttpResponse(build_template_workbook(), content_type=XLSX_MIME)
    response['Content-Disposition'] = 'attachment; filename="project-import-template.xlsx"'
    return response


@login_required
@require_POST
def preview_project_workbook(request):
    if not _can_use_project_workbooks(request.user):
        return HttpResponseForbidden('You are not authorized to import project workbooks.')
    upload = request.FILES.get('workbook')
    if upload is None:
        messages.error(request, 'Choose an .xlsx workbook to upload.')
        return redirect('assign_projects')
    preview = validate_workbook(read_workbook(upload), actor=request.user)
    preview_token = sign_preview(preview, actor_id=request.user.id) if preview.is_valid else ''
    return render(request, 'manager/project_workbook_preview.html', {
        'preview': preview,
        'preview_token': preview_token,
    })


@login_required
@require_POST
def apply_project_workbook(request):
    if not _can_use_project_workbooks(request.user):
        return HttpResponseForbidden('You are not authorized to import project workbooks.')
    try:
        preview = unsign_preview(request.POST.get('preview_token', ''), actor_id=request.user.id)
        result = apply_workbook_preview(preview, actor=request.user)
    except PermissionError:
        return HttpResponseForbidden('This workbook preview belongs to another user.')
    except (PreviewTokenError, WorkbookImportError) as exc:
        return HttpResponseBadRequest(str(exc))
    except PermissionDenied as exc:
        return HttpResponseForbidden(str(exc))
    messages.success(
        request,
        f'Workbook applied: {result.created_projects} projects created, '
        f'{result.updated_projects} updated, {result.created_tasks} tasks created, '
        f'and {result.updated_tasks} updated.',
    )
    for warning in result.warnings:
        messages.warning(request, warning)
    return redirect('assign_projects')


def _client_label_for_cost_centre(cost_centre):
    return cost_centre.client_name or cost_centre.company_name or cost_centre.name


def _normalize_client_label(label):
    return ' '.join((label or '').strip().lower().split())


@login_required
def manager_dashboard(request):
    now = timezone.now()
    base_qs = visible_notifications_for(request.user)

    # New since last login (NO slice here)
    last_login = getattr(request.user, 'last_login', None)
    new_count = base_qs.filter(created_at__gt=last_login).count() if last_login else 0

    # Final list to display (slice AFTER ordering)
    my_notifications = base_qs[:10]

    return render(request, 'manager/manager_dashboard.html', {
        'my_notifications': my_notifications,
        'new_notifications_count': new_count,
    })


@login_required
def manager_engagements(request):
    if not can_manage_client_engagements(request.user):
        return HttpResponseForbidden('You are not authorized to manage client engagement notes.')
    project_scope = manageable_projects_for(
        request.user,
        Project.objects.select_related('research_centre', 'assigned_user', 'created_by'),
    )
    cost_centres = CostCentre.objects.select_related('research_centre').order_by('name')

    if getattr(request.user, 'research_centre_id', None):
        cost_centres = cost_centres.filter(research_centre_id=request.user.research_centre_id)

    if request.method == 'POST':
        form = EngagementLogForm(request.POST, user=request.user, projects=project_scope)
        if form.is_valid():
            log = form.save(commit=False)
            if log.project_id not in set(project_scope.values_list('id', flat=True)):
                form.add_error('project', 'Please choose one of the projects already assigned to you for this research centre.')
            else:
                log.entered_by = request.user
                log.research_centre = (
                    log.cost_centre.research_centre
                    if log.cost_centre else log.project.research_centre
                ) or getattr(request.user, 'research_centre', None)
                log.save()
                if log.next_follow_up_date:
                    FinancialProject.objects.filter(project=log.project).update(
                        next_follow_up_date=log.next_follow_up_date,
                    )
                    follow_up_task = log.project.tasks.order_by('created_at').first()
                    if follow_up_task:
                        follow_up_task.due_date = log.next_follow_up_date
                        follow_up_task.save(update_fields=['due_date'])
                messages.success(request, 'Engagement history saved and pushed into the CRM view.')
                query = f"project={log.project_id}"
                if log.cost_centre_id:
                    query = f"cost_centre={log.cost_centre_id}&{query}"
                return redirect(f"{reverse('manager_engagements')}?{query}")
    else:
        initial = {}
        if request.GET.get('project'):
            initial['project'] = request.GET.get('project')
        if request.GET.get('cost_centre'):
            initial['cost_centre'] = request.GET.get('cost_centre')
        form = EngagementLogForm(initial=initial, user=request.user, projects=project_scope)

    selected_cost_centre_id = request.POST.get('cost_centre') or request.GET.get('cost_centre')
    selected_project_id = request.POST.get('project') or request.GET.get('project')

    logs = EngagementLog.objects.select_related(
        'project', 'cost_centre', 'research_centre', 'entered_by'
    ).filter(project__in=project_scope)

    if selected_cost_centre_id:
        logs = logs.filter(cost_centre_id=selected_cost_centre_id)
    if selected_project_id:
        logs = logs.filter(project_id=selected_project_id)

    selected_cost_centre = cost_centres.filter(id=selected_cost_centre_id).first() if selected_cost_centre_id else None
    prior_client_logs = EngagementLog.objects.none()
    previously_approached_by = []
    if selected_cost_centre:
        client_key = _normalize_client_label(_client_label_for_cost_centre(selected_cost_centre))
        if client_key:
            prior_client_logs = list(EngagementLog.objects.select_related(
                'project', 'cost_centre', 'research_centre', 'entered_by'
            ).order_by('-engagement_date', '-created_at'))
            prior_client_logs = [
                entry for entry in prior_client_logs
                if _normalize_client_label(entry.client_label) == client_key
            ]
            previously_approached_by = sorted({
                entry.research_centre.name
                for entry in prior_client_logs
                if entry.research_centre
            })

    context = {
        'engagement_form': form,
        'engagement_projects': project_scope.order_by('-created_at', 'name'),
        'engagement_cost_centres': cost_centres,
        'engagement_logs': logs.order_by('-engagement_date', '-created_at')[:20],
        'selected_cost_centre': selected_cost_centre,
        'selected_project_id': int(selected_project_id) if str(selected_project_id).isdigit() else None,
        'prior_client_logs': prior_client_logs,
        'previously_approached_by': previously_approached_by,
    }
    return render(request, 'manager/manager_engagements.html', context)



@login_required
def app_kanban(request):
    phases = ["UX/UI", "Architecture", "Frontend", "Backend", "Testing", "Deployment"]
    return render(request, 'manager/app_kanban.html', {'phases': phases})


@login_required
def manager_ganttchart(request):
    projects = manageable_projects_for(
        request.user,
        Project.objects.select_related('assigned_user', 'created_by').prefetch_related(
            'tasks__assigned_to', 'tasks__subtasks'
        ),
    )
    detail_mode = request.GET.get('detail') == 'tasks'
    timeline_items = []

    for project in projects:
        project_tasks = list(project.tasks.all())
        if not detail_mode or not project_tasks:
            start_date = timezone.localdate(project.created_at) if project.created_at else timezone.localdate()
            task_dates = [task.due_date for task in project_tasks if task.due_date]
            end_date = max(task_dates) if task_dates else (project.due_date or start_date + timedelta(days=3))
            owner = project.assigned_user or project.created_by
            timeline_items.append({
                'id': f'project-{project.id}',
                'name': project.name,
                'project': project.name,
                'owner': owner.get_full_name() or owner.username if owner else 'Unassigned',
                'ownerId': owner.id if owner else '',
                'status': project.get_status_display(),
                'progress': round(sum(task.progress for task in project_tasks) / len(project_tasks)) if project_tasks else 0,
                'startDate': start_date,
                'endDate': end_date if end_date >= start_date else start_date,
            })
            continue

        for task in project_tasks:
            start_date = timezone.localdate(task.created_at) if task.created_at else timezone.localdate(project.created_at)
            end_date = task.due_date or project.due_date or start_date + timedelta(days=3)
            owner = task.assigned_to or project.assigned_user or project.created_by
            timeline_items.append({
                'id': f'task-{task.id}',
                'name': task.title,
                'project': project.name,
                'owner': owner.get_full_name() or owner.username if owner else 'Unassigned',
                'ownerId': owner.id if owner else '',
                'status': task.get_status_display(),
                'progress': task.progress,
                'startDate': start_date,
                'endDate': end_date if end_date >= start_date else start_date,
            })

    first_date = min((item['startDate'] for item in timeline_items), default=timezone.localdate())
    gantt_tasks = []
    for item in timeline_items:
        start = (item['startDate'] - first_date).days + 1
        end = (item['endDate'] - first_date).days + 1
        gantt_tasks.append({
            'id': item['id'],
            'name': item['name'],
            'project': item['project'],
            'owner': item['owner'],
            'ownerId': item['ownerId'],
            'status': item['status'],
            'progress': item['progress'],
            'start': start,
            'end': max(start, end),
            'startLabel': item['startDate'].strftime('%Y-%m-%d'),
            'endLabel': item['endDate'].strftime('%Y-%m-%d'),
        })

    staff_users = CustomUser.objects.filter(
        id__in=[item['ownerId'] for item in gantt_tasks if item['ownerId']]
    ).order_by('first_name', 'last_name', 'username')
    return render(request, 'adminpanel/admin_ganttchart.html', {
        'projects': projects,
        'is_gantt_readonly': True,
        'gantt_detail_mode': detail_mode,
        'gantt_tasks_json': json.dumps(gantt_tasks),
        'gantt_staff_users': staff_users,
        'gantt_base_template': 'manager/home.html',
        'gantt_back_url': reverse('manager_dashboard'),
        'gantt_back_label': 'Back to Dashboard',
        'gantt_page_title': 'My Project Timeline',
    })


@login_required
def manager_gantt_all_data(request):
    projects = manageable_projects_for(request.user).prefetch_related('tasks__parent_task')

    data = []
    detail_mode = request.GET.get('detail') == 'tasks'

    for project in projects:
        project_tasks = list(project.tasks.all())
        if not detail_mode:
            start = timezone.localdate(project.created_at) if project.created_at else timezone.localdate()
            task_due_dates = [task.due_date for task in project_tasks if task.due_date]
            end = max(task_due_dates) if task_due_dates else (project.due_date or start)
            data.append({
                'id': f'P{project.id}', 'name': project.name,
                'start': start.isoformat(), 'end': max(start, end).isoformat(),
                'progress': round(sum(task.progress for task in project_tasks) / len(project_tasks)) if project_tasks else 0,
                'dependencies': None, 'custom_class': f'project-{project.id}',
            })
            continue
        for task in project_tasks:
            data.append({
                "id": f"T{task.id}",
                "name": f"{project.name}: {task.title}",
                "start": task.created_at.strftime('%Y-%m-%d'),
                "end": task.due_date.strftime('%Y-%m-%d') if task.due_date else task.created_at.strftime('%Y-%m-%d'),
                "progress": task.progress or 0,
                "dependencies": f"T{task.parent_task.id}" if task.parent_task else None,
                "custom_class": f"project-{project.id}"  # For visual separation if needed
            })

    return JsonResponse(data, safe=False)


TASK_TYPES = ['UX/UI', 'Architecture', 'Frontend', 'Backend', 'Testing', 'Deployment', 'Paper', 'Book', 'Other']


def _kanban_projects_for(user):
    """Projects that can be selected from the user's editable Kanban."""
    scoped_projects = scope_projects_for_user(Project.objects.all(), user)
    assigned_project_ids = assigned_projects_for(user, scoped_projects).values('id')
    return scoped_projects.filter(
        Q(id__in=assigned_project_ids) | Q(created_by=user)
    ).distinct()

@login_required
def manager_kanban(request):
    status_labels = {
        'todo': 'To Do',
        'in_progress': 'In Progress',
        'review': 'Review',
        'done': 'Done',
    }
    statuses = list(status_labels.keys())
    priorities = ['Low', 'Medium', 'High']

    # Include tasks created by, directly assigned to, or belonging to projects
    # managed/assigned to this user through either assignment relationship.
    scoped_projects = scope_projects_for_user(Project.objects.all(), request.user)
    managed_projects = scoped_projects.filter(created_by=request.user)
    workable_task_ids = workable_tasks_for(request.user).filter(
        Q(project__in=scoped_projects) | Q(project__isnull=True)
    ).values('id')
    tasks = Task.objects.filter(
        Q(id__in=workable_task_ids) | Q(project__in=managed_projects)
    ).distinct()
    
    #Group tasks by their status
    tasks_by_status = defaultdict(list)
    for task in tasks:
        tasks_by_status[task.status].append(task)

    # Match the staff Kanban assignment behavior while retaining manager-owned projects.
    projects = _kanban_projects_for(request.user)


    context = {
        'statuses': statuses,
        'status_labels': status_labels,
        'priorities': priorities,
        'grouped_tasks': dict(tasks_by_status),
        'task_types': TASK_TYPES,
        'projects': projects,
        'today': now().date(),
        'kanban_base_template': (
            'adminpanel/index.html'
            if has_role(request.user, 'admin', 'centrehead')
            else 'manager/home.html'
        ),
        'kanban_title': (
            'My Financial Projects Kanban'
            if getattr(request, '_financial_board', False)
            else 'My Editable Project Kanban'
            if has_role(request.user, 'centrehead')
            else 'Project Manager Kanban'
        ),
        'kanban_intro': (
            'Update the client bids and other project tasks assigned to you.'
            if getattr(request, '_financial_board', False)
            else 'Update tasks in projects assigned to you or managed by you.'
            if has_role(request.user, 'centrehead')
            else 'Track and manage tasks for your assigned projects.'
        ),
    }
    return render(request, 'manager/manager_kanban.html', context)


@login_required
def financial_kanban(request):
    if not has_role(request.user, 'financialadmin'):
        return HttpResponseForbidden('This Kanban is reserved for Financial Admin project work.')

    request._financial_board = True
    return manager_kanban(request)

    # tasks = Task.objects.filter(created_by=request.user)
    # tasks_by_status = defaultdict(list)
    # for task in tasks:
    #     tasks_by_status[task.status].append(task)

    # context = {
    #     'statuses': statuses,
    #     'status_labels': status_labels,
    #     'priorities': priorities,
    #     'grouped_tasks': dict(tasks_by_status),
    #     'task_types': TASK_TYPES,
    #     'projects': Project.objects.all(),
    #     'today': now().date(),
    # }
    # return render(request, 'manager/manager_kanban.html', context)


@login_required
def assign_projects_view(request):
    if not can_manage_projects(request.user):
        return HttpResponseForbidden('You are not authorized to manage projects.')
    User = get_user_model()  # define User
    project_id = request.GET.get('project_id')

    # Projects where the current user is creator or (acting) manager
    projects = manageable_projects_for(request.user)

    selected_project = None
    assignments = None
    assignment_form = None
    project_team_users = User.objects.none()  
    task_form = None
    project_form = ProjectForm()

    # Ensure the allocation list contains only users the actor may manage.
    eligible_team_users = User.objects.filter(is_active=True).exclude(role='student')
    if not has_role(request.user, 'admin', 'dean'):
        centre_id = getattr(request.user, 'research_centre_id', None)
        eligible_team_users = (
            eligible_team_users.filter(research_centre_id=centre_id)
            if centre_id else eligible_team_users.none()
        )
    for u in eligible_team_users:
        TeamMember.objects.get_or_create(
            user=u,
            defaults={
                "full_name": (f"{u.first_name} {u.last_name}".strip() or u.username),
                "role": "Team Member",
            },
        )

    if project_id:
        selected_project = get_object_or_404(projects, id=project_id)

        # Prefetch to avoid N+1 when listing assignments
        assignments = selected_project.assignments.select_related("team_member__user")

        assignment_form = AssignmentForm(project=selected_project, user=request.user)

        # users on this project's team
        team_user_ids = Assignment.objects.filter(project=selected_project)\
            .values_list("team_member__user_id", flat=True)
        project_team_users = User.objects.filter(id__in=team_user_ids)

        # task form limited to this project's team + tasks
        task_form = TaskForm(project=selected_project)

    context = {
        "projects": projects,
        "project": selected_project,
        "assignments": assignments,
        "assignment_form": assignment_form,
        "project_team_users": project_team_users,  # use this in the template if you keep manual selects
        "project_form": project_form,
        "task_form": task_form,
        "project_lead_users": eligible_team_users.order_by('first_name', 'last_name', 'username'),
        "workspace_title": (
            'Centre Project Management'
            if has_role(request.user, 'centrehead') and not has_role(request.user, 'admin')
            else 'Project Manager Assignment'
        ),
        "workspace_back_url": (
            reverse('overview')
            if has_role(request.user, 'admin', 'centrehead')
            else reverse('manager_dashboard')
        ),
    }
    return render(request, "manager/assign.html", context)


@login_required
def create_project(request):
    if not can_manage_projects(request.user):
        return HttpResponseForbidden('You are not authorized to create projects.')
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                project = form.save(commit=False)
                project.created_by = request.user
                if has_role(request.user, 'manager') and not has_role(request.user, 'admin', 'centrehead', 'financialadmin'):
                    project.assigned_user = request.user
                project.research_centre = getattr(request.user, 'research_centre', None)
                project.save()
                if project.project_type == 'book':
                    try:
                        total_chapters = max(1, int(request.POST.get('book_total_chapters') or 1))
                    except (TypeError, ValueError):
                        total_chapters = 1
                    Book.objects.get_or_create(
                        project=project,
                        defaults={
                            'title': project.name,
                            'description': project.description,
                            'status': 'writing',
                            'due_date': project.due_date,
                            'lead_author': (
                                request.POST.get('book_lead_author', '').strip()
                                or request.user.get_full_name()
                                or request.user.username
                            ),
                            'total_chapters': total_chapters,
                            'created_by': request.user,
                        },
                    )
            messages.success(request, 'Project created successfully!')
            return redirect('assign_projects') 
    return redirect('assign_projects')



@login_required
def assign_team_member(request, project_id):
    if not can_manage_projects(request.user):
        return HttpResponseForbidden('You are not authorized to allocate projects.')
    project = get_object_or_404(manageable_projects_for(request.user), id=project_id)
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, project=project, user=request.user)
       
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.project = project
            assignment.save()
            email_sent = notify_project_assignment(
                request=request,
                project=project,
                recipient=assignment.team_member.user,
                responsibility=assignment.responsibility,
            )
            messages.success(request, f"{assignment.team_member} assigned!")
            if not email_sent:
                messages.warning(request, "The assignment was saved, but its email could not be delivered.")
            return redirect(f"{reverse('assign_projects')}?project_id={project.id}")
        else:
            messages.error(request, 'Assignment failed. Please check the form.')

            projects = scope_projects_for_user(Project.objects.filter(
                models.Q(created_by=request.user) | models.Q(assigned_user=request.user)
            ), request.user).distinct()

            assignments = project.assignments.all()
            eligible_users = get_user_model().objects.exclude(role='student')
            if getattr(request.user, 'research_centre_id', None):
                eligible_users = eligible_users.filter(research_centre_id=request.user.research_centre_id)
            project_form = ProjectForm()

            context = {
                'projects': projects,
                'project': project,
                'assignments': assignments,
                'assignment_form': form,
                'eligible_users': eligible_users,
                'project_form': project_form,
            }
            return render(request, 'manager/assign.html', context)

    return redirect(f"{reverse('assign_projects')}?project_id={project.id}")


@login_required
def remove_assignment(request, assignment_id):
    if not can_manage_projects(request.user):
        return HttpResponseForbidden('You are not authorized to remove project allocations.')
    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        project__in=manageable_projects_for(request.user),
    )
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, 'Team member removed.')
        return redirect(f"{reverse('assign_projects')}?project_id={assignment.project.id}")
    

@login_required
def add_task(request, project_id):
    if not can_manage_projects(request.user):
        return HttpResponseForbidden('You are not authorized to manage project tasks.')
    allowed_projects = manageable_projects_for(request.user)
    if has_role(request.user, 'financialadmin') and not has_role(request.user, 'admin'):
        allowed_projects = allowed_projects.filter(
            Q(assigned_user=request.user) | Q(created_by=request.user)
        )
    project = get_object_or_404(allowed_projects.distinct(), id=project_id)
    if request.method == 'POST':
        form = TaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.created_by = request.user
            task.save()
            messages.success(request, 'Task created successfully!')
            return redirect(f"{reverse('assign_projects')}?project_id={project.id}")
        else:
            # Form has errors - render the page with error messages displayed
            messages.error(request, 'Please fix the errors in the task form.')
            User = get_user_model()
            projects = manageable_projects_for(request.user)
            project_lead_users = User.objects.filter(is_active=True).exclude(role='student')
            if not has_role(request.user, 'admin', 'dean'):
                centre_id = getattr(request.user, 'research_centre_id', None)
                project_lead_users = (
                    project_lead_users.filter(research_centre_id=centre_id)
                    if centre_id else project_lead_users.none()
                )
            assignments = project.assignments.select_related("team_member__user")
            assignment_form = AssignmentForm(project=project, user=request.user)
            project_form = ProjectForm()
            
            context = {
                'projects': projects,
                'project': project,
                'assignments': assignments,
                'assignment_form': assignment_form,
                'task_form': form,  # Pass the form WITH errors
                'project_form': project_form,
                'project_lead_users': project_lead_users.order_by('first_name', 'last_name', 'username'),
                'workspace_title': 'Centre Project Management' if has_role(request.user, 'centrehead') else 'Project Manager Assignment',
                'workspace_back_url': reverse('overview') if has_role(request.user, 'admin', 'centrehead') else reverse('manager_dashboard'),
            }
            return render(request, 'manager/assign.html', context)
    
    return redirect('assign_projects')


# @login_required
# def add_task(request, project_id):
#     print("-------------------",project_id)
#     project = get_object_or_404(
#         Project.objects.filter(
#             Q(id=project_id) & (Q(created_by=request.user) | Q(assigned_user=request.user))
#         )
#     )
    
#     if request.method == 'POST':
#         title = request.POST.get('title')
#         priority = request.POST.get('priority')
#         due_date = request.POST.get('due_date') or None
#         status = request.POST.get('status')
#         task_type = request.POST.get('task_type')
#         assigned_to_id = request.POST.get('assigned_to') or None
#         parent_task_id = request.POST.get('parent_task') or None

#         assigned_to = None

#         if assigned_to_id:
#             # Must be on the project team
#             team_user_ids = Assignment.objects.filter(project=project)\
#                                 .values_list('team_member__user_id', flat=True)
#             if int(assigned_to_id) not in team_user_ids:
#                 messages.error(request, 'Selected user is not a member of this project.')
#                 return redirect(f"{reverse('assign_projects')}?project_id={project.id}")
#             assigned_to = get_user_model().objects.get(id=assigned_to_id)

#         parent_task = Task.objects.get(id=parent_task_id) if parent_task_id else None

        # if assigned_to_id:
        #     assigned_to = get_user_model().objects.get(id=assigned_to_id)

        # if parent_task_id:
        #     parent_task = Task.objects.get(id=parent_task_id)

    #     Task.objects.create(
    #         title=title,
    #         priority=priority,
    #         due_date=due_date,
    #         status=status,
    #         task_type=task_type,
    #         created_by=request.user,
    #         project=project,
    #         assigned_to=assigned_to,
    #         parent_task=parent_task
    #     )
    #     messages.success(request, 'Task created successfully!')
    #     return redirect(f"{reverse('assign_projects')}?project_id={project.id}")

    # return redirect('assign_projects')
  

@login_required
@require_POST
def edit_task(request, task_id):
    task = get_object_or_404(workable_tasks_for(request.user), id=task_id)
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    title = (request.POST.get('title') or '').strip()
    status = request.POST.get('status')
    priority = request.POST.get('priority') or None
    task_type = request.POST.get('task_type') or None
    due_date = request.POST.get('due_date') or None
    project_id = request.POST.get('project')

    errors = []
    if not title:
        errors.append('Task title is required.')
    if status not in dict(Task.STATUS_CHOICES):
        errors.append('Choose a valid task status.')
    if priority and priority not in dict(Task.PRIORITY_CHOICES):
        errors.append('Choose a valid priority.')
    if task_type and task_type not in dict(Task.PROJECT_PHASES):
        errors.append('Choose a valid task type.')
    parsed_due_date = None
    if due_date:
        try:
            parsed_due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        except ValueError:
            errors.append('Choose a valid due date.')

    project = None
    if project_id:
        project = _kanban_projects_for(request.user).filter(id=project_id).first()
        if project is None:
            errors.append('You cannot move this task to that project.')

    if errors:
        if wants_json:
            return JsonResponse({'success': False, 'error': ' '.join(errors)}, status=400)
        for error in errors:
            messages.error(request, error)
        return redirect('manager_kanban')

    task.title = title
    task.status = status
    task.priority = priority
    task.due_date = parsed_due_date
    task.task_type = task_type
    task.project = project
    task.save()

    if wants_json:
        return JsonResponse({
            'success': True,
            'message': 'Task saved successfully.',
            'task': {
                'id': task.id,
                'title': task.title,
                'status': task.status,
                'progress': task.progress,
                'project_name': task.project.name if task.project else '',
                'task_type': task.task_type or '',
                'priority': task.priority or '',
                'due_date': task.due_date.isoformat() if task.due_date else '',
            },
        })

    messages.success(request, 'Task saved successfully.')
    return redirect('manager_kanban')

@login_required
@require_POST
def update_task_status(request, task_id):
    try:
        task = get_object_or_404(workable_tasks_for(request.user), id=task_id)
        if not can_update_task(request.user, task):
            return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
        data = json.loads(request.body)
        new_status = data.get('status')
        if new_status not in dict(Task.STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
        task.status = new_status
        task.save(update_fields=['status', 'progress'])
        return JsonResponse({
            'success': True,
            'message': 'Task status saved successfully.',
            'progress': task.progress,
        })
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)


@login_required
def manager_delete_task(request, task_id):
    task = get_object_or_404(workable_tasks_for(request.user), id=task_id)
    
    if request.method == 'POST':
        task.delete()
    return redirect('manager_kanban')
    
@login_required
def add_learning_resource(request):
    if request.method == 'POST' and request.user.role == 'manager':
        title = request.POST['title']
        type_ = request.POST['type']
        platform = request.POST['platform']
        platform_logo = request.POST['platform_logo']
        description = request.POST['description']
        link = request.POST['link']

        LearningContent.objects.create(
            title=title,
            type=type_,
            platform=platform,
            platform_logo=platform_logo,
            description=description,
            link=link,
            added_by=request.user
        )
        messages.success(request, 'Resource added successfully.')
    return redirect('manager_elearning')

@login_required
def elearning_page(request):
    resource_type = request.GET.get('type', '').strip()
    search_query = request.GET.get('search', '').strip()


    resources = LearningContent.objects.all()

    if resource_type and resource_type.lower() != "all":
        resources = resources.filter(type__icontains=resource_type)

    if search_query:
        resources = resources.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    resources = resources.order_by('-created_at')
    distinct_types = LearningContent.objects.values_list('type', flat=True).distinct()


    print("Type:", resource_type)
    print("Search:", search_query)
    print("Final count:", resources.count())


    return render(request, 'manager/manager_elearning.html', {
        'resources': resources,
        'selected_type': resource_type or 'All',
        'search_query': search_query,
        'resource_types': distinct_types,  # NEW!
    })


@login_required
def templates_page(request):
    search_query = request.GET.get('search', '').strip()

    book_templates = Template.objects.filter(category='Book')
    research_templates = Template.objects.filter(category='Research')
    software_templates = Template.objects.filter(category='Software')

    if search_query:
        book_templates = book_templates.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
        research_templates = research_templates.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
        software_templates = software_templates.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    categories = {
        'Book Templates': book_templates,
        'Research Papers': research_templates,
        'Software Development': software_templates,
    }

    return render(request, 'manager/manager_templates.html', {
        'template_categories': categories,
        'search_query': search_query
    })



@login_required
def add_template(request):
    if request.method == 'POST' and request.user.role == 'manager':
        title = request.POST['title']
        description = request.POST['description']
        category = request.POST['category']
        file = request.FILES['file']

        if file:
            template = Template.objects.create(
                title=title,
                description=description,
                category=category,
                file=file,
                uploaded_by=request.user
            )
            # Create SystemMedia record for template
            MediaService.create_media_record(
                file_obj=file,
                uploaded_by=request.user,
                purpose='template',
                description=f"Template: {title} ({category})",
                related_object=template
            )
    return redirect('manager_templates')

@login_required
def edit_template(request, pk):
    template = get_object_or_404(Template, pk=pk, uploaded_by=request.user)
    if request.method == 'POST':
        template.title = request.POST['title']
        template.description = request.POST['description']
        template.category = request.POST['category']
        if 'file' in request.FILES:
            new_file = request.FILES['file']
            template.file = new_file
            # Create SystemMedia record for updated file
            MediaService.create_media_record(
                file_obj=new_file,
                uploaded_by=request.user,
                purpose='template',
                description=f"Template: {template.title} ({template.category}) [Updated]",
                related_object=template
            )
        template.save()
        return redirect('manager_templates')
    return render(request, 'manager/edit_template.html', {'template': template})


@login_required
def delete_template(request, pk):
    template = get_object_or_404(Template, pk=pk, uploaded_by=request.user)
    if request.method == 'POST':
        template.delete()
    return redirect('manager_templates')

@login_required
def manager_journal(request):
    if not can_manage_publications(request.user):
        return HttpResponseForbidden('You are not authorized to manage publications.')
    papers = scope_outputs_for_user(Paper.objects.all(), request.user)
    internal_papers = papers.filter(internal_external='internal')
    external_papers = papers.filter(internal_external='external')
    return render(request, 'manager/manager_journal.html', {
        'internal_papers': internal_papers,
        'external_papers': external_papers,
    })


@login_required
def add_paper(request):
    if not can_manage_publications(request.user):
        return HttpResponseForbidden('You are not authorized to upload publications.')
    if request.method == 'POST':
        print("POST DATA:", request.POST.dict())  

        status = request.POST.get('paperStatus')
        paper_type = request.POST.get('paperType')
        
        if not status or not paper_type:
            messages.error(request, "Missing required fields.")
            return redirect('manager_journal')

        paper = Paper.objects.create(
            title=request.POST.get('paperTitle'),
            internal_external=paper_type,
            paper_type='journal' if 'journal' in (request.POST.get('targetJournal') or '').lower() else 'conference',
            status=status,
            version=request.POST.get('currentVersion'),
            lead_author=request.POST.get('leadAuthor'),
            co_authors=request.POST.get('coAuthors'),
            target_journal=request.POST.get('targetJournal'),
            submission_date=request.POST.get('submissionDate') or None,
            abstract=request.POST.get('paperAbstract'),
            manuscript=request.FILES.get('paperFile'),
            created_by=request.user,
        )
        sync_publication_project(paper, actor=request.user)
        
        # Create SystemMedia record for manuscript if provided
        if paper.manuscript:
            MediaService.create_media_record(
                file_obj=paper.manuscript,
                uploaded_by=request.user,
                purpose='manuscript',
                description=f"Manuscript: {paper.title}",
                related_object=paper
            )

        messages.success(request, "Paper added successfully.")
        return redirect('manager_journal')

    
@login_required
def upload_excel_papers(request):
    if not can_manage_publications(request.user):
        return HttpResponseForbidden('You are not authorized to import publications.')
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        df = pd.read_excel(excel_file)

        for _, row in df.iterrows():
            Paper.objects.create(
                title=row.get('Title'),
                internal_external=row.get('Type', '').lower(),
                paper_type=row.get('Paper Type', 'journal').lower(),
                status=row.get('Status', 'draft').lower(),
                version=row.get('Version', '1.0'),
                lead_author=row.get('Lead Author', ''),
                co_authors=row.get('Co Authors', ''),
                target_journal=row.get('Target Journal', ''),
                submission_date=row.get('Submission Date'),
                abstract=row.get('Abstract', ''),
                created_by=request.user
            )

        messages.success(request, "Papers uploaded successfully from Excel.")
    return redirect('manager_journal')

@login_required
def edit_paper(request, paper_id):
    if not can_manage_publications(request.user):
        return HttpResponseForbidden('You are not authorized to edit publications.')
    paper = get_object_or_404(scope_outputs_for_user(Paper.objects.all(), request.user), id=paper_id)
    if request.method == 'POST':
        paper.title = request.POST.get('paperTitle')
        paper.status = request.POST.get('paperStatus')
        paper.version = request.POST.get('currentVersion')
        paper.lead_author = request.POST.get('leadAuthor')
        paper.co_authors = request.POST.get('coAuthors')
        paper.target_journal = request.POST.get('targetJournal')
        paper.submission_date = request.POST.get('submissionDate')
        paper.abstract = request.POST.get('paperAbstract')
        if request.FILES.get('paperFile'):
            paper.manuscript = request.FILES['paperFile']
        paper.save()
        messages.success(request, "Paper updated successfully.")
        return redirect('manager_journal')
    return render(request, 'manager/edit_paper.html', {'paper': paper})

@require_POST
@login_required
def delete_paper(request, paper_id):
    if not can_manage_publications(request.user):
        return HttpResponseForbidden('You are not authorized to delete publications.')
    paper = get_object_or_404(scope_outputs_for_user(Paper.objects.all(), request.user), id=paper_id)
    paper.delete()
    messages.success(request, "Paper deleted.")
    return redirect('manager_journal')

@require_POST
@login_required
def edit_paper_ajax(request, paper_id):
    """Handle paper edit via Django form with validation"""
    if not can_manage_publications(request.user):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    try:
        paper = get_object_or_404(scope_outputs_for_user(Paper.objects.all(), request.user), id=paper_id)
        
        # Capture old M2M values before form processing
        old_co_authors = set(paper.co_authors_users.values_list('id', flat=True))
        old_reviewers = set(paper.assigned_reviewers.values_list('id', flat=True))
        
        # Use PaperForm for proper validation and handling of all field types
        form = PaperForm(request.POST, request.FILES, instance=paper)
        
        if form.is_valid():
            # Set the changed_by user for signal processing
            paper._changed_by = request.user
            
            # Capture new M2M values after form processes them
            new_co_authors = set(form.cleaned_data.get('co_authors_users', []).values_list('id', flat=True))
            new_reviewers = set(form.cleaned_data.get('assigned_reviewers', []).values_list('id', flat=True))
            
            # Set M2M change flags
            if old_co_authors != new_co_authors:
                paper._co_authors_changed = {
                    'old': list(paper.co_authors_users.all()),
                    'new': list(form.cleaned_data.get('co_authors_users', []))
                }
            
            if old_reviewers != new_reviewers:
                paper._reviewers_changed = {
                    'old': list(paper.assigned_reviewers.all()),
                    'new': list(form.cleaned_data.get('assigned_reviewers', []))
                }
            
            # Form.save() automatically handles all field types including ForeignKey and M2M
            form.save()
            return JsonResponse({'success': True, 'message': 'Paper updated successfully'})
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
def manager_book(request):
    books = scope_books_for_user(Book.objects.all(), request.user).order_by('-created_at')
    return render(request, 'manager/manager_book.html', {
        'books': books,
        'unlinked_publication_count': books.filter(project__isnull=True).count(),
    })


@csrf_exempt
@login_required
def add_book(request):
    if not can_manage_publications(request.user):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            book = Book.objects.create(
                title=data.get('title'),
                lead_author=data.get('lead_author'),
                due_date=data.get('due_date') or None,
                description=data.get('description'),
                total_chapters=data.get('total_chapters') or 0,
                completed_chapters=data.get('completed_chapters') or 0,
                publisher=data.get('publisher'),
                status=data.get('status'),
                created_by=request.user if request.user.is_authenticated else None,
            )
            sync_publication_project(book, actor=request.user)
            return JsonResponse({'success': True, 'book_id': book.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
@login_required
def edit_book(request, book_id):
    try:
        book = scope_books_for_user(Book.objects.all(), request.user).get(id=book_id)
        if request.method == 'POST':
            data = json.loads(request.body)
            print(f"DEBUG: Received data for book {book_id}: {data}")
            print(f"DEBUG: Old status: {book.status}")
            
            form = BookForm(data, instance=book)
            if form.is_valid():
                updated_book = form.save()
                sync_publication_project(updated_book, actor=request.user)
                updated_book.refresh_from_db()
                print(f"DEBUG: Book {book_id} saved successfully")
                print(f"DEBUG: New status in DB: {updated_book.status}")
                return JsonResponse({'success': True, 'book_id': book_id, 'new_status': updated_book.status})
            else:
                print(f"DEBUG: Form validation failed: {form.errors}")
                print(f"DEBUG: Form clean errors: {form.non_field_errors()}")
                return JsonResponse({'success': False, 'errors': dict(form.errors)})
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    except Exception as e:
        print(f"DEBUG: Error in edit_book: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@login_required
def delete_book(request, book_id):
    if request.method == 'POST':
        scope_books_for_user(Book.objects.filter(id=book_id), request.user).delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'})


@csrf_exempt
@login_required
def get_chapters(request, book_id):
    book = get_object_or_404(scope_books_for_user(Book.objects.all(), request.user), id=book_id)
    chapters = scope_chapters_for_user(Chapter.objects.filter(book=book), request.user).select_related('assigned_author').order_by("chapter_number")
    chapter_list = [
        {
            "id": c.id,
            "book_id": c.book_id,
            "chapter_number": c.chapter_number,
            "title": c.title,
            "author": c.author,
            "assigned_author_id": c.assigned_author_id,
            "assigned_author": (c.assigned_author.get_full_name() or c.assigned_author.username) if c.assigned_author else c.author,
            "editor": c.editor,
            "status": c.status,
            "last_updated": c.last_updated.strftime("%Y-%m-%d %H:%M")
        } for c in chapters
    ]
    return JsonResponse({"chapters": chapter_list})

@login_required
@require_POST
def add_chapter(request, book_id):
    if not has_role(request.user, 'admin', 'centrehead', 'manager'):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    if request.method == "POST":
        data = json.loads(request.body)
        book = scope_books_for_user(Book.objects.all(), request.user).get(id=book_id)
        author_lookup = {'id': data.get('assigned_author_id')} if data.get('assigned_author_id') else {'username__iexact': str(data.get('author', '')).strip()}
        assigned_author = get_object_or_404(User, is_active=True, **author_lookup)
        chapter = Chapter.objects.create(
            book=book,
            chapter_number=data["chapter_number"],
            title=data["title"],
            author=assigned_author.get_full_name() or assigned_author.username,
            assigned_author=assigned_author,
            editor=data.get("editor", ""),
            status=data["status"]
        )
        print("Chapter created:", chapter.title)

        return JsonResponse({"success": True, "id": chapter.id})
    return JsonResponse({"success": False, "error": "Invalid request method"})

@login_required
@require_POST
def edit_chapter(request, chapter_id):
    if not has_role(request.user, 'admin', 'centrehead', 'manager'):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    if request.method == "POST":
        data = json.loads(request.body)
        try:
            chapter = Chapter.objects.get(id=chapter_id, book__in=scope_books_for_user(Book.objects.all(), request.user))
            chapter.chapter_number = data["chapter_number"]
            chapter.title = data["title"]
            author_lookup = {'id': data.get('assigned_author_id')} if data.get('assigned_author_id') else {'username__iexact': str(data.get('author', '')).strip()}
            assigned_author = get_object_or_404(User, is_active=True, **author_lookup)
            chapter.assigned_author = assigned_author
            chapter.author = assigned_author.get_full_name() or assigned_author.username
            chapter.editor = data.get("editor", "")
            chapter.status = data["status"]
            chapter.save()
            return JsonResponse({"success": True})
        except Chapter.DoesNotExist:
            return JsonResponse({"success": False, "error": "Chapter not found"})
    return JsonResponse({"success": False, "error": "Invalid request method"})

@login_required
@require_POST
def delete_chapter(request, chapter_id):
    if not has_role(request.user, 'admin', 'centrehead', 'manager'):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    if request.method == "POST":
        Chapter.objects.filter(id=chapter_id, book__in=scope_books_for_user(Book.objects.all(), request.user)).delete()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Invalid request"})


@require_POST
@login_required
def bulk_assign_chapters(request, book_id):
    """Create/update chapter assignments in one atomic, validated request."""
    if not has_role(request.user, 'admin', 'centrehead', 'manager'):
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    book = get_object_or_404(scope_books_for_user(Book.objects.all(), request.user), id=book_id)
    try:
        rows = json.loads(request.body).get('chapters', [])
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)
    if not isinstance(rows, list) or not rows:
        return JsonResponse({'success': False, 'error': 'Provide at least one chapter'}, status=400)

    validated_rows = []
    valid_statuses = dict(Chapter.STATUS_CHOICES)
    for row in rows:
        if not str(row.get('chapter_number', '')).isdigit() or not str(row.get('title', '')).strip():
            return JsonResponse({'success': False, 'error': 'Each chapter needs a number and title'}, status=400)
        author_lookup = {'id': row.get('assigned_author_id')} if row.get('assigned_author_id') else {'username__iexact': str(row.get('assigned_author_username', '')).strip()}
        author = get_object_or_404(User, is_active=True, **author_lookup)
        if book.created_by_id and book.created_by.research_centre_id and author.research_centre_id != book.created_by.research_centre_id:
            return JsonResponse({'success': False, 'error': 'Authors must belong to the book research centre'}, status=400)
        status = row.get('status', 'Draft')
        if status not in valid_statuses:
            return JsonResponse({'success': False, 'error': f'Invalid chapter status: {status}'}, status=400)
        validated_rows.append((row, author, status))

    from django.db import transaction
    saved = []
    with transaction.atomic():
        for row, author, status in validated_rows:
            chapter, _created = Chapter.objects.update_or_create(
                book=book,
                chapter_number=row.get('chapter_number'),
                defaults={
                    'title': str(row.get('title', '')).strip(),
                    'assigned_author': author,
                    'author': author.get_full_name() or author.username,
                    'editor': str(row.get('editor', '')).strip(),
                    'status': status,
                },
            )
            saved.append(chapter.id)
    return JsonResponse({'success': True, 'saved': len(saved), 'chapter_ids': saved})


@login_required
def get_paper_comments(request, paper_id):
    """Get or add comments for a paper"""
    paper = get_object_or_404(scope_outputs_for_user(Paper.objects.all(), request.user), id=paper_id)
    
    if request.method == 'POST':
        # Add new comment
        try:
            data = json.loads(request.body)
            text = data.get('text', '').strip()
            
            if not text:
                return JsonResponse({'success': False, 'error': 'Comment cannot be empty'})
            
            comment = PaperComment.objects.create(
                paper=paper,
                user=request.user,
                text=text
            )
            
            return JsonResponse({'success': True, 'comment_id': comment.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    elif request.method == 'GET':
        # Fetch comments
        try:
            # Get active (non-archived) comments
            active_comments = PaperComment.objects.filter(
                paper=paper,
                archived=False
            ).order_by('-created_at')
            
            # Get archived comments
            archived_comments = PaperComment.objects.filter(
                paper=paper,
                archived=True
            ).order_by('-created_at')
            
            def format_comments(comments):
                return [{
                    'id': c.id,
                    'user': c.user.get_full_name() or c.user.username,
                    'text': c.text,
                    'created_at': c.created_at.strftime('%I:%M %p'),  # 2:34 PM format
                    'created_date': c.created_at.strftime('%b %d, %Y'),  # Feb 03, 2026
                    'timestamp': c.created_at.isoformat()
                } for c in comments]
            
            return JsonResponse({
                'success': True,
                'comments': format_comments(active_comments),
                'archived_comments': format_comments(archived_comments),
                'archived_count': archived_comments.count()
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@login_required
def get_paper_form_html(request, paper_id):
    """Return the rendered Django form HTML for editing a paper"""
    try:
        paper = get_object_or_404(scope_outputs_for_user(Paper.objects.all(), request.user), id=paper_id)
        form = PaperForm(instance=paper)
        
        from django.template.loader import render_to_string
        html = render_to_string('includes/paper_form.html', {'form': form})
        
        return JsonResponse({
            'success': True,
            'form_html': html
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def get_paper_data(request, paper_id):
    """Return paper data as JSON for populating the edit form"""
    try:
        paper = get_object_or_404(scope_outputs_for_user(Paper.objects.all(), request.user), id=paper_id)
        
        # Serialize co_authors_users and assigned_reviewers IDs
        co_authors_ids = list(paper.co_authors_users.values_list('id', flat=True))
        reviewers_ids = list(paper.assigned_reviewers.values_list('id', flat=True))
        
        data = {
            'id': paper.id,
            'title': paper.title,
            'paper_type': paper.paper_type,
            'internal_external': paper.internal_external,
            'status': paper.status,
            'version': paper.version,
            'lead_author': paper.lead_author,
            'co_authors': paper.co_authors or '',
            'lead_author_user': paper.lead_author_user_id,
            'co_authors_users': co_authors_ids,
            'assigned_reviewers': reviewers_ids,
            'abstract': paper.abstract or '',
            'target_journal': paper.target_journal or '',
            'submission_date': paper.submission_date.isoformat() if paper.submission_date else '',
            'decision_date': paper.decision_date.isoformat() if paper.decision_date else '',
            'feedback_text': paper.feedback_text or '',
        }
        
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})
