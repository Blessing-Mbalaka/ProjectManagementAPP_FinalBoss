# views.py in manager app
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.db import models
from projects.models import Project, Task, Assignment,TeamMember
from projects.forms import ProjectForm, AssignmentForm, TaskForm
from .models import LearningContent, Template, Paper, Book, Chapter, PaperComment
from .forms import BookForm
from django.http import JsonResponse
from django.contrib import messages
from datetime import datetime
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
from django.utils import timezone
from django.shortcuts import render
from adminpanel.models import Notification

User = get_user_model()


@login_required
def manager_dashboard(request):
    now = timezone.now()
    user_role = getattr(request.user, 'role', None)

    # Build base queryset (active window + audience for THIS user)
    base_qs = (Notification.objects
        .filter(
            Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=now),
            Q(expires_at__isnull=True)   | Q(expires_at__gt=now),
        )
        .filter(
            Q(audience='all') |
            Q(audience='role', audience_role=user_role) |
            Q(audience='specific', recipients=request.user)
        )
        .select_related('created_by')
        .prefetch_related('recipients')
        .distinct()  # in case M2M joins duplicate rows
    )

    # New since last login (NO slice here)
    last_login = getattr(request.user, 'last_login', None)
    new_count = base_qs.filter(created_at__gt=last_login).count() if last_login else 0

    # Final list to display (slice AFTER ordering)
    my_notifications = base_qs.order_by('-is_pinned', '-created_at')[:10]

    return render(request, 'manager/manager_dashboard.html', {
        'my_notifications': my_notifications,
        'new_notifications_count': new_count,
    })



@login_required
def app_kanban(request):
    phases = ["UX/UI", "Architecture", "Frontend", "Backend", "Testing", "Deployment"]
    return render(request, 'manager/app_kanban.html', {'phases': phases})


@login_required
def manager_ganttchart(request):
    projects = Project.objects.filter(
        Q(created_by=request.user) | Q(assigned_user=request.user)
    ).distinct()

    return render(request, 'manager/manager_ganttchart.html', {'projects': projects})


@login_required
def manager_gantt_all_data(request):
    projects = Project.objects.filter(
        Q(created_by=request.user) | Q(assigned_user=request.user)
    ).distinct()

    data = []

    for project in projects:
        for task in project.tasks.all():
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

    #Fetch all tasks created by the manager or from projects tehy created/assigned
    tasks = Task.objects.filter(Q(created_by=request.user) | Q(project__created_by=request.user) | Q(project__assigned_user=request.user))
    
    #Group tasks by their status
    tasks_by_status = defaultdict(list)
    for task in tasks:
        tasks_by_status[task.status].append(task)

    # Include all projects the manager is involved in (created or assigned)
    projects = Project.objects.filter(
        Q(created_by=request.user) |
        Q(assigned_user=request.user)
    ).distinct()


    context = {
        'statuses': statuses,
        'status_labels': status_labels,
        'priorities': priorities,
        'grouped_tasks': dict(tasks_by_status),
        'task_types': TASK_TYPES,
        'projects': projects,
        'today': now().date(),
    }
    return render(request, 'manager/manager_kanban.html', context)

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
    User = get_user_model()  # define User
    project_id = request.GET.get('project_id')

    # Projects where the current user is creator or (acting) manager
    projects = Project.objects.filter(
        Q(created_by=request.user) | Q(assigned_user=request.user)
    ).distinct()

    selected_project = None
    assignments = None
    assignment_form = None
    project_team_users = User.objects.none()  
    task_form = None
    project_form = ProjectForm()

    # (Optional) ensure TeamMember exists for each user
    # Better: move to a post_save signal; kept here for now
    for u in User.objects.all():
        TeamMember.objects.get_or_create(
            user=u,
            defaults={
                "full_name": (f"{u.first_name} {u.last_name}".strip() or u.username),
                "role": "Team Member",
            },
        )

    if project_id:
        selected_project = get_object_or_404(
            Project,
            Q(created_by=request.user) | Q(assigned_user=request.user),
            id=project_id,
        )

        # Prefetch to avoid N+1 when listing assignments
        assignments = selected_project.assignments.select_related("team_member__user")

        assignment_form = AssignmentForm(project=selected_project)

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
    }
    return render(request, "manager/assign.html", context)


@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            messages.success(request, 'Project created successfully!')
            return redirect('assign_projects') 
    return redirect('assign_projects')



@login_required
def assign_team_member(request, project_id):
    project = get_object_or_404(
        Project.objects.filter(
            models.Q(created_by=request.user) | models.Q(assigned_user=request.user),
            id=project_id
        )
    )
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, project=project)
       
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.project = project
            assignment.save()
            messages.success(request, f"{assignment.team_member} assigned!")
            return redirect(f"{reverse('assign_projects')}?project_id={project.id}")
        else:
            messages.error(request, 'Assignment failed. Please check the form.')

            projects = Project.objects.filter(
                models.Q(created_by=request.user) | models.Q(assigned_user=request.user)
            ).distinct()

            assignments = project.assignments.all()
            eligible_users = get_user_model().objects.exclude(role='student')
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
    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        project__in=Project.objects.filter(
            Q(created_by=request.user) | Q(assigned_user=request.user)
        )
    )
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, 'Team member removed.')
        return redirect(f"{reverse('assign_projects')}?project_id={assignment.project.id}")
    

@login_required
def add_task(request, project_id):
    project = get_object_or_404(
        Project.objects.filter(Q(id=project_id) & (Q(created_by=request.user) | Q(assigned_user=request.user)))
    )
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
            projects = Project.objects.filter(
                Q(created_by=request.user) | Q(assigned_user=request.user)
            ).distinct()
            assignments = project.assignments.select_related("team_member__user")
            assignment_form = AssignmentForm(project=project)
            project_form = ProjectForm()
            
            context = {
                'projects': projects,
                'project': project,
                'assignments': assignments,
                'assignment_form': assignment_form,
                'task_form': form,  # Pass the form WITH errors
                'project_form': project_form,
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
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if request.method == 'POST':
        task.title = request.POST.get('title')
        task.priority = request.POST.get('priority')
        task.due_date = request.POST.get('due_date') or None
        task.task_type = request.POST.get('task_type')
        project_id = request.POST.get('project')
        task.project = Project.objects.filter(id=project_id).first() if project_id else None
        task.save()
        return redirect('manager_kanban')

@csrf_exempt
@login_required
def update_task_status(request, task_id):
    if request.method == 'POST':
        try:
            task = get_object_or_404(Task, id=task_id)
            data = json.loads(request.body)
            new_status = data.get('status')

            if new_status in ['todo', 'in_progress', 'review', 'done']:
                task.status = new_status
                task.save()
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)


@login_required
def manager_delete_task(request, task_id):
    task = get_object_or_404(
        Task,
        Q(created_by=request.user) | Q(project__assigned_user=request.user),
        id=task_id
    )
    
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
    internal_papers = Paper.objects.filter(internal_external='internal')
    external_papers = Paper.objects.filter(internal_external='external')
    return render(request, 'manager/manager_journal.html', {
        'internal_papers': internal_papers,
        'external_papers': external_papers,
    })


@login_required
def add_paper(request):
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
    paper = get_object_or_404(Paper, id=paper_id)
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
    paper = get_object_or_404(Paper, id=paper_id)
    paper.delete()
    messages.success(request, "Paper deleted.")
    return redirect('manager_journal')

@require_POST
@login_required
def edit_paper_ajax(request, paper_id):
    paper = get_object_or_404(Paper, id=paper_id)

    paper.title = request.POST.get('paperTitle')
    paper.status = request.POST.get('paperStatus')
    paper.version = request.POST.get('currentVersion')
    paper.lead_author = request.POST.get('leadAuthor')
    paper.co_authors = request.POST.get('coAuthors')
    paper.target_journal = request.POST.get('targetJournal')
    paper.submission_date = request.POST.get('submissionDate') or None
    paper.abstract = request.POST.get('paperAbstract')

    if request.FILES.get('paperFile'):
        paper.manuscript = request.FILES['paperFile']

    paper.save()
    return JsonResponse({'success': True})

@login_required
def manager_book(request):
    books = Book.objects.all().order_by('-created_at')  # You can filter by user if needed
    return render(request, 'manager/manager_book.html', {'books': books})


@csrf_exempt
def add_book(request):
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
                status=data.get('status')
            )
            return JsonResponse({'success': True, 'book_id': book.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Invalid request'})


@csrf_exempt
def edit_book(request, book_id):
    try:
        book = Book.objects.get(id=book_id)
        if request.method == 'POST':
            data = json.loads(request.body)
            print(f"DEBUG: Received data for book {book_id}: {data}")
            print(f"DEBUG: Old status: {book.status}")
            
            form = BookForm(data, instance=book)
            if form.is_valid():
                updated_book = form.save()
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
def delete_book(request, book_id):
    if request.method == 'POST':
        Book.objects.filter(id=book_id).delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid method'})


@csrf_exempt
def get_chapters(request, book_id):
    chapters = Chapter.objects.filter(book_id=book_id).order_by("chapter_number")
    chapter_list = [
        {
            "id": c.id,
            "book_id": c.book_id,
            "chapter_number": c.chapter_number,
            "title": c.title,
            "author": c.author,
            "editor": c.editor,
            "status": c.status,
            "last_updated": c.last_updated.strftime("%Y-%m-%d %H:%M")
        } for c in chapters
    ]
    return JsonResponse({"chapters": chapter_list})

@csrf_exempt
def add_chapter(request, book_id):
    if request.method == "POST":
        data = json.loads(request.body)
        book = Book.objects.get(id=book_id)
        chapter = Chapter.objects.create(
            book=book,
            chapter_number=data["chapter_number"],
            title=data["title"],
            author=data["author"],
            editor=data.get("editor", ""),
            status=data["status"]
        )
        print("Chapter created:", chapter.title)

        return JsonResponse({"success": True, "id": chapter.id})
    return JsonResponse({"success": False, "error": "Invalid request method"})

@csrf_exempt
def edit_chapter(request, chapter_id):
    if request.method == "POST":
        data = json.loads(request.body)
        try:
            chapter = Chapter.objects.get(id=chapter_id)
            chapter.chapter_number = data["chapter_number"]
            chapter.title = data["title"]
            chapter.author = data["author"]
            chapter.editor = data.get("editor", "")
            chapter.status = data["status"]
            chapter.save()
            return JsonResponse({"success": True})
        except Chapter.DoesNotExist:
            return JsonResponse({"success": False, "error": "Chapter not found"})
    return JsonResponse({"success": False, "error": "Invalid request method"})

@csrf_exempt
def delete_chapter(request, chapter_id):
    if request.method == "POST":
        Chapter.objects.filter(id=chapter_id).delete()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Invalid request"})


@login_required
def get_paper_comments(request, paper_id):
    """Get or add comments for a paper"""
    paper = get_object_or_404(Paper, id=paper_id)
    
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


