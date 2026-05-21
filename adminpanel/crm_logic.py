from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

from django.db.models import F, Q, Sum
from django.utils import timezone

from manager.models import Book, Paper
from projects.models import Project
from users.models import CustomUser

from .models import CostCentre, Expenditure, ResearchCentre


CRM_TABS = [
    ('clients', 'Clients', 'bi-building'),
    ('centres', 'Centres', 'bi-diagram-3'),
    ('engagements', 'Engagements', 'bi-kanban'),
    ('directory', 'Directory', 'bi-journal-text'),
    ('financials', 'Financials', 'bi-cash-stack'),
    ('alerts', 'Alerts', 'bi-exclamation-triangle'),
    ('reports', 'Reports', 'bi-bar-chart'),
]


def safe_decimal(value, default=Decimal('0.00')):
    if value is None:
        return default
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def get_user_research_centre_id(user):
    return getattr(user, 'research_centre_id', None)


def get_selected_centre(request):
    if request.user.role == 'centrehead':
        return ResearchCentre.objects.filter(id=get_user_research_centre_id(request.user)).first()
    centre_id = request.GET.get('centre')
    return ResearchCentre.objects.filter(id=centre_id).first() if centre_id else None


def get_scope(request):
    selected_centre = get_selected_centre(request)
    research_centres = ResearchCentre.objects.all().order_by('name')
    if request.user.role == 'centrehead':
        research_centres = research_centres.filter(id=get_user_research_centre_id(request.user))

    cost_centres = CostCentre.objects.select_related('research_centre').all().order_by('name')
    users = CustomUser.objects.select_related('research_centre').filter(is_active=True).order_by('first_name', 'last_name', 'username')
    projects = Project.objects.select_related('assigned_user', 'created_by').prefetch_related('tasks', 'assignments__team_member__user').all().order_by('-created_at')
    papers = Paper.objects.select_related('lead_author_user', 'created_by').prefetch_related('co_authors_users').all().order_by('-updated_at')
    books = Book.objects.prefetch_related('chapters').select_related('created_by').all().order_by('-created_at')

    if selected_centre:
        cost_centres = cost_centres.filter(research_centre=selected_centre)
        users = users.filter(research_centre=selected_centre)
        projects = projects.filter(
            Q(assigned_user__research_centre=selected_centre)
            | Q(created_by__research_centre=selected_centre)
            | Q(assignments__team_member__user__research_centre=selected_centre)
        ).distinct()
        papers = papers.filter(
            Q(lead_author_user__research_centre=selected_centre)
            | Q(created_by__research_centre=selected_centre)
            | Q(co_authors_users__research_centre=selected_centre)
        ).distinct()
        books = books.filter(created_by__research_centre=selected_centre)

    return {
        'selected_centre': selected_centre,
        'research_centres': research_centres,
        'cost_centres': cost_centres,
        'users': users,
        'projects': projects,
        'papers': papers,
        'books': books,
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


def paper_authors(paper):
    authors = []
    if paper.lead_author_user:
        authors.append(paper.lead_author_user.get_full_name() or paper.lead_author_user.username)
    elif paper.lead_author:
        authors.append(paper.lead_author)
    authors.extend([user.get_full_name() or user.username for user in paper.co_authors_users.all()])
    if paper.co_authors:
        authors.extend([name.strip() for name in paper.co_authors.split(',') if name.strip()])
    return ', '.join(dict.fromkeys(authors))


def build_clients(cost_centres, users):
    clients = []
    total_revenue = Decimal('0.00')
    total_spent = Decimal('0.00')
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
            'visibility': 'Institutional',
        })
    return clients, total_revenue, total_spent


def build_engagements(projects):
    today = timezone.now().date()
    engagements = []
    for project in projects:
        tasks = list(project.tasks.all())
        latest_task = max((task.created_at for task in tasks), default=project.created_at)
        stage = {'planning': 'Prospect', 'on-hold': 'On hold', 'completed': 'Completed'}.get(project.status, 'Active')
        engagements.append({
            'id': project.id,
            'name': project.name,
            'client': project_centre_name(project),
            'stage': stage,
            'status': project.status,
            'lead': project.assigned_user or project.created_by,
            'due_date': project.due_date,
            'last_contact': latest_task,
            'progress': project_progress(project),
            'team_count': project.assignments.count(),
            'visibility': 'Institutional',
            'is_overdue': bool(project.due_date and project.due_date < today and project.status != 'completed'),
        })
    return engagements


def build_publications(papers, books, projects):
    publications = []
    for paper in papers:
        publications.append({
            'type': paper.get_paper_type_display(),
            'title': paper.title,
            'status': paper.get_status_display(),
            'authors': paper_authors(paper),
            'owner': paper.created_by,
            'updated_at': paper.updated_at,
        })
    for book in books:
        publications.append({
            'type': 'Book',
            'title': book.title,
            'status': book.get_status_display(),
            'authors': book.lead_author,
            'owner': book.created_by,
            'updated_at': book.created_at,
        })
    for project in projects:
        if project.project_type in ['book', 'paper']:
            publications.append({
                'type': dict(Project.PROJECT_TYPES).get(project.project_type, project.project_type),
                'title': project.name,
                'status': project.get_status_display(),
                'authors': (project.assigned_user or project.created_by).get_full_name() if (project.assigned_user or project.created_by) else '',
                'owner': project.assigned_user or project.created_by,
                'updated_at': project.created_at,
            })
    return publications


def build_reports(clients, centres, engagements, alerts, publications, users):
    revenue_by_centre = defaultdict(lambda: Decimal('0.00'))
    pipeline_by_centre = defaultdict(lambda: Decimal('0.00'))
    client_count_by_centre = defaultdict(int)
    for client in clients:
        revenue_by_centre[client['sector']] += client['total_received']
        pipeline_by_centre[client['sector']] += client['pipeline_value']
        client_count_by_centre[client['sector']] += 1

    return {
        'revenue_by_centre': dict(revenue_by_centre),
        'pipeline_by_centre': dict(pipeline_by_centre),
        'client_count_by_centre': dict(client_count_by_centre),
        'engagement_status': dict(Counter(item['stage'] for item in engagements)),
        'staff_by_centre': dict(Counter(user.research_centre.name if user.research_centre else 'Unassigned' for user in users)),
        'publications_by_type': dict(Counter(item['type'] for item in publications)),
        'alerts_by_type': dict(Counter(item['type'] for item in alerts)),
        'centre_performance': {centre['name']: centre['avg_progress'] for centre in centres},
    }


def chart_payload(reporting):
    def chart(label, values):
        return {'labels': list(values.keys()), 'data': [float(value) for value in values.values()], 'label': label}

    return {
        'revenueByCentre': chart('Revenue by centre', reporting['revenue_by_centre']),
        'pipelineByCentre': chart('Pipeline by centre', reporting['pipeline_by_centre']),
        'engagementStatus': chart('Engagement status', reporting['engagement_status']),
        'clientCountByCentre': chart('Clients by centre', reporting['client_count_by_centre']),
        'staffByCentre': chart('Staff by centre', reporting['staff_by_centre']),
        'publicationsByType': chart('Publications by type', reporting['publications_by_type']),
        'alertsByType': chart('Alerts by type', reporting['alerts_by_type']),
        'centrePerformance': chart('Centre performance', reporting['centre_performance']),
    }


def build_context(request, active_tab):
    scope = get_scope(request)
    cost_centres = list(scope['cost_centres'])
    users = list(scope['users'])
    projects = list(scope['projects'])
    papers = list(scope['papers'])
    books = list(scope['books'])
    clients, total_revenue, total_spent = build_clients(cost_centres, users)
    engagements = build_engagements(projects)

    centres = []
    for centre in scope['research_centres']:
        centre_users = [user for user in users if user.research_centre_id == centre.id]
        centre_clients = [client for client in clients if client['sector'] == centre.name]
        centre_engagements = [engagement for engagement in engagements if engagement['client'] == centre.name]
        revenue = sum((client['total_received'] for client in centre_clients), Decimal('0.00'))
        spent = sum((client['total_spent'] for client in centre_clients), Decimal('0.00'))
        centres.append({
            'id': centre.id,
            'name': centre.name,
            'director': next((user for user in centre_users if user.role == 'centrehead'), None),
            'staff_count': len(centre_users),
            'client_count': len(centre_clients),
            'engagement_count': len(centre_engagements),
            'revenue': revenue,
            'estimated_profit': revenue - spent,
            'avg_progress': int(sum(item['progress'] for item in centre_engagements) / len(centre_engagements)) if centre_engagements else 0,
        })

    alerts = []
    for engagement in engagements:
        if engagement['is_overdue']:
            alerts.append({'level': 'High', 'type': 'Deadline', 'message': f"{engagement['name']} is past its due date.", 'owner': engagement['lead']})
        if engagement['last_contact'] and (timezone.now() - engagement['last_contact']).days > 60 and engagement['status'] != 'completed':
            alerts.append({'level': 'Medium', 'type': 'Contact Risk', 'message': f"{engagement['name']} has no recent activity in 60+ days.", 'owner': engagement['lead']})
    for cost_centre in cost_centres:
        if cost_centre.get_total_received() <= 0:
            alerts.append({'level': 'Medium', 'type': 'Payment', 'message': f"{cost_centre.name} has no recorded payments.", 'owner': None})
    for expenditure in Expenditure.objects.select_related('cost_centre').filter(cost_centre__in=cost_centres, oracle_balance__isnull=False).exclude(oracle_balance=F('amount'))[:20]:
        alerts.append({'level': 'High', 'type': 'Oracle', 'message': f"{expenditure.cost_centre.name}: Oracle balance differs for {expenditure.name}.", 'owner': None})

    names = defaultdict(list)
    for client in clients:
        names[client['name'].lower()].append(client)
    for duplicates in names.values():
        centre_names = {client['sector'] for client in duplicates}
        if len(duplicates) > 1 and len(centre_names) > 1:
            alerts.append({'level': 'Medium', 'type': 'Overlap', 'message': f"{duplicates[0]['name']} appears across multiple centres.", 'owner': None})

    publications = build_publications(papers, books, projects)
    reporting = build_reports(clients, centres, engagements, alerts, publications, users)
    active_engagements = [item for item in engagements if item['status'] in ['planning', 'in-progress']]

    return {
        **scope,
        'active_tab': active_tab,
        'crm_tabs': CRM_TABS,
        'clients': clients,
        'centres': centres,
        'engagements': engagements,
        'directory_engagements': [item for item in engagements if item['visibility'] != 'Private'],
        'alerts': alerts,
        'staff_directory': users,
        'publications': publications,
        'reporting': reporting,
        'crm_chart_data': chart_payload(reporting),
        'role_counts': Counter(user.role for user in users),
        'total_revenue': total_revenue,
        'total_spent': total_spent,
        'pipeline_value': sum((client['pipeline_value'] for client in clients), Decimal('0.00')),
        'estimated_profit': total_revenue - total_spent,
        'active_engagement_count': len(active_engagements),
        'client_count': len(clients),
    }
