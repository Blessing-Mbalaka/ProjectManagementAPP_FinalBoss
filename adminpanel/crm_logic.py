from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import F, Q, Sum
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from manager.models import Book, Conference, Paper
from projects.models import Project
from projects.scope import output_centre_q, project_centre_q
from users.models import CustomUser

from .models import CostCentre, Expenditure, ResearchCentre


CRM_TABS = [
    ('clients', 'Clients', 'bi-building'),
    ('centres', 'Centres', 'bi-diagram-3'),
    ('engagements', 'Engagements', 'bi-kanban'),
    ('directory', 'Directory', 'bi-journal-text'),
    ('financials', 'Financials', 'bi-cash-stack'),
    ('active_projects', 'Active Projects', 'bi-list-task'),
    ('alerts', 'Alerts', 'bi-exclamation-triangle'),
    ('reports', 'Reports', 'bi-bar-chart'),
]

CRM_WELCOME = {
    'clients': ('CRM Clients', 'Review institutional client relationships, ownership, pipeline, and current revenue.'),
    'centres': ('CRM Centres', 'Compare centre leadership, staff coverage, client load, and engagement progress.'),
    'engagements': ('CRM Engagements', 'Track relationship activity, delivery stage, due dates, and workload status.'),
    'directory': ('CRM Directory', 'Read the staff and publication directory connected to active CRM work.'),
    'financials': ('CRM Financials', 'Monitor revenue, spend, pipeline, and estimated profit across centres.'),
    'active_projects': ('CRM Active Projects', 'Inspect active delivery work and the alerts attached to each project.'),
    'alerts': ('CRM Alerts', 'Review relationship, payment, deadline, and data quality risks.'),
    'reports': ('CRM Reports', 'Export and inspect institutional CRM reporting summaries.'),
}


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
    if request.user.role == 'admin' and get_user_research_centre_id(request.user):
        return ResearchCentre.objects.filter(id=get_user_research_centre_id(request.user)).first()
    centre_id = request.GET.get('centre')
    return ResearchCentre.objects.filter(id=centre_id).first() if centre_id else None


def get_scope(request):
    selected_centre = get_selected_centre(request)
    research_centres = ResearchCentre.objects.all().order_by('name')
    if request.user.role == 'centrehead':
        research_centres = research_centres.filter(id=get_user_research_centre_id(request.user))
    if request.user.role == 'admin' and get_user_research_centre_id(request.user):
        research_centres = research_centres.filter(id=get_user_research_centre_id(request.user))

    cost_centres = CostCentre.objects.select_related('research_centre').all().order_by('name')
    users = CustomUser.objects.select_related('research_centre').filter(is_active=True).order_by('first_name', 'last_name', 'username')
    projects = Project.objects.select_related('assigned_user', 'created_by', 'research_centre').prefetch_related('tasks', 'assignments__team_member__user').all().order_by('-created_at')
    papers = Paper.objects.select_related('lead_author_user', 'created_by').prefetch_related('co_authors_users').all().order_by('-updated_at')
    conferences = Conference.objects.select_related('lead_author_user', 'created_by').prefetch_related('co_authors_users').all().order_by('-updated_at')
    books = Book.objects.prefetch_related('chapters').select_related('created_by').all().order_by('-created_at')

    if selected_centre:
        cost_centres = cost_centres.filter(research_centre=selected_centre)
        users = users.filter(research_centre=selected_centre)
        projects = projects.filter(project_centre_q(selected_centre)).distinct()
        papers = papers.filter(output_centre_q(selected_centre)).distinct()
        conferences = conferences.filter(output_centre_q(selected_centre)).distinct()
        books = books.filter(created_by__research_centre=selected_centre)

    return {
        'selected_centre': selected_centre,
        'research_centres': research_centres,
        'cost_centres': cost_centres,
        'users': users,
        'projects': projects,
        'papers': papers,
        'conferences': conferences,
        'books': books,
    }


def project_progress(project):
    tasks = list(project.tasks.all())
    if not tasks:
        return 0
    return int(sum(task.progress for task in tasks) / len(tasks))


def project_centre_name(project):
    if project.research_centre:
        return project.research_centre.name
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
            'name': cost_centre.client_name or cost_centre.company_name or cost_centre.name,
            'cost_centre_name': cost_centre.name,
            'company_name': cost_centre.company_name,
            'company_registration_number': cost_centre.company_registration_number,
            'vat_number': cost_centre.vat_number,
            'industry': cost_centre.industry,
            'company_website': cost_centre.company_website,
            'company_email': cost_centre.company_email,
            'company_phone': cost_centre.company_phone,
            'company_address': cost_centre.company_address,
            'contact_person_name': cost_centre.contact_person_name,
            'contact_person_role': cost_centre.contact_person_role,
            'contact_email': cost_centre.contact_email,
            'contact_phone': cost_centre.contact_phone,
            'crm_notes': cost_centre.crm_notes,
            'phase_due_dates': [
                ('Phase 1', cost_centre.phase_1_due_date),
                ('Phase 2', cost_centre.phase_2_due_date),
                ('Phase 3', cost_centre.phase_3_due_date),
                ('Phase 4', cost_centre.phase_4_due_date),
            ],
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


def build_publications(papers, conferences, books, projects):
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
    for conference in conferences:
        publications.append({
            'type': 'Conference',
            'title': conference.title,
            'status': conference.get_status_display(),
            'authors': paper_authors(conference),
            'owner': conference.created_by,
            'updated_at': conference.updated_at,
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


def client_risk_explainer():
    return [
        'Overdue active project dates raise client delivery risk.',
        'Missing or overdue client phase due dates on the cost centre/MOA record raise delivery-governance risk.',
        'No project activity for 60+ days raises retention risk.',
        'Missing recorded payments or outstanding MOA value raises payment and renewal risk.',
        'Oracle amount mismatches and duplicate clients across centres raise data-quality risk.',
        'This is a rules-based score now; it is structured so a future trained churn model can replace or supplement the score.',
    ]


def send_dean_alert_email_once(request, alerts):
    if request.user.role != 'dean' or not alerts or not getattr(request.user, 'email', None):
        return

    today_key = timezone.now().strftime('%Y%m%d')
    session_key = f'crm_dean_alert_email_sent_{today_key}'
    if request.session.get(session_key):
        return

    if not getattr(settings, 'EMAIL_USE_CONSOLE', False):
        email_host_user = getattr(settings, 'EMAIL_HOST_USER', '')
        email_host_password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        if not email_host_user or not email_host_password:
            request.session[session_key] = True
            return

    high_alerts = [alert for alert in alerts if alert.get('level') == 'High']
    subject = 'CRM risk alerts need review'
    lines = [
        f'{len(alerts)} CRM alert(s) are currently visible in your CRM scope.',
        f'{len(high_alerts)} high severity alert(s).',
        '',
    ]
    for alert in alerts[:10]:
        lines.append(f"- {alert.get('level')}: {alert.get('type')} - {alert.get('message')}")

    try:
        send_mail(
            subject,
            '\n'.join(lines),
            getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            [request.user.email],
            fail_silently=True,
        )
        request.session[session_key] = True
    except BaseException:
        request.session[session_key] = True
        pass


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
    conferences = list(scope['conferences'])
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

    client_risk_alerts = []
    publication_risk_alerts = []
    for engagement in engagements:
        if engagement['is_overdue']:
            alert = {'level': 'High', 'type': 'Client Risk', 'message': f"{engagement['name']} is past its due date.", 'owner': engagement['lead'], 'engagement_id': engagement['id']}
            client_risk_alerts.append(alert)
            if engagement['status'] != 'completed':
                publication_type = next((project.project_type for project in projects if project.id == engagement['id']), None)
                if publication_type in ['book', 'paper']:
                    publication_risk_alerts.append({'level': 'High', 'type': 'Publication Deadline', 'message': f"{engagement['name']} is overdue and may affect publication delivery.", 'owner': engagement['lead'], 'engagement_id': engagement['id']})
        if engagement['last_contact'] and (timezone.now() - engagement['last_contact']).days > 60 and engagement['status'] != 'completed':
            client_risk_alerts.append({'level': 'Medium', 'type': 'Client Risk', 'message': f"{engagement['name']} has no recent activity in 60+ days.", 'owner': engagement['lead'], 'engagement_id': engagement['id']})
    for cost_centre in cost_centres:
        if cost_centre.get_total_received() <= 0:
            client_risk_alerts.append({'level': 'Medium', 'type': 'Client Risk', 'message': f"{cost_centre.name} has no recorded payments.", 'owner': None})
        phase_dates = [
            ('Phase 1', cost_centre.phase_1_due_date),
            ('Phase 2', cost_centre.phase_2_due_date),
            ('Phase 3', cost_centre.phase_3_due_date),
            ('Phase 4', cost_centre.phase_4_due_date),
        ]
        if safe_decimal(cost_centre.moa_amount) > 0:
            missing_phases = [label for label, due_date in phase_dates if not due_date]
            if missing_phases:
                client_risk_alerts.append({
                    'level': 'Medium',
                    'type': 'Client Risk',
                    'message': f"{cost_centre.name} is missing due dates for {', '.join(missing_phases)}.",
                    'owner': None,
                })
        for phase_label, due_date in phase_dates:
            if due_date and due_date < timezone.now().date():
                client_risk_alerts.append({
                    'level': 'High',
                    'type': 'Client Risk',
                    'message': f"{cost_centre.name} {phase_label} due date passed on {due_date}.",
                    'owner': None,
                })
    for expenditure in Expenditure.objects.select_related('cost_centre').filter(cost_centre__in=cost_centres, oracle_balance__isnull=False).exclude(oracle_balance=F('amount'))[:20]:
        client_risk_alerts.append({'level': 'High', 'type': 'Client Risk', 'message': f"{expenditure.cost_centre.name}: Oracle balance differs for {expenditure.name}.", 'owner': None})

    names = defaultdict(list)
    for client in clients:
        names[client['name'].lower()].append(client)
    for duplicates in names.values():
        centre_names = {client['sector'] for client in duplicates}
        if len(duplicates) > 1 and len(centre_names) > 1:
            client_risk_alerts.append({'level': 'Medium', 'type': 'Client Risk', 'message': f"{duplicates[0]['name']} appears across multiple centres.", 'owner': None})

    stale_cutoff = timezone.now() - timedelta(days=60)
    for paper in papers:
        if paper.status not in ['published', 'accepted', 'rejected'] and paper.updated_at < stale_cutoff:
            publication_risk_alerts.append({'level': 'Medium', 'type': 'Publication Risk', 'message': f"{paper.title} has had no paper update in 60+ days.", 'owner': paper.created_by})
    for conference in conferences:
        if conference.status not in ['presented', 'accepted', 'rejected'] and conference.updated_at < stale_cutoff:
            publication_risk_alerts.append({'level': 'Medium', 'type': 'Publication Risk', 'message': f"{conference.title} has had no conference update in 60+ days.", 'owner': conference.created_by})
    for book in books:
        if book.due_date and book.due_date < timezone.now().date() and book.status != 'published':
            publication_risk_alerts.append({'level': 'High', 'type': 'Publication Risk', 'message': f"{book.title} is past its book due date.", 'owner': book.created_by})

    alerts = client_risk_alerts + publication_risk_alerts
    publications = build_publications(papers, conferences, books, projects)
    reporting = build_reports(clients, centres, engagements, alerts, publications, users)
    active_engagements = [item for item in engagements if item['status'] in ['planning', 'in-progress']]
    active_alert_counts = Counter(alert.get('engagement_id') for alert in alerts if alert.get('engagement_id'))
    for engagement in active_engagements:
        engagement['alert_count'] = active_alert_counts.get(engagement['id'], 0)
        engagement['risk_level'] = 'High' if engagement['is_overdue'] else ('Medium' if engagement['alert_count'] else 'Low')

    send_dean_alert_email_once(request, alerts)

    return {
        **scope,
        'active_tab': active_tab,
        'crm_tabs': CRM_TABS,
        'crm_welcome': CRM_WELCOME.get(active_tab, CRM_WELCOME['clients']),
        'clients': clients,
        'centres': centres,
        'engagements': engagements,
        'active_projects': active_engagements,
        'directory_engagements': [item for item in engagements if item['visibility'] != 'Private'],
        'alerts': alerts,
        'client_risk_alerts': client_risk_alerts,
        'publication_risk_alerts': publication_risk_alerts,
        'client_risk_explainer': client_risk_explainer(),
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
