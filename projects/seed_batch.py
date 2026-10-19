"""Batched persistence for the reviewed 2026 seed (not a general workbook importer)."""
from datetime import date
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.utils import timezone
from manager.models import Book, Paper
from projects.models import Assignment, Project, Task, TeamMember
from projects.workbook_import.application import ImportResult
from projects.workbook_import.validation import normalize_name


def apply_seed_batch(preview, *, actor):
    if preview.errors or preview.warnings or actor.id != preview.actor_id or actor.role != 'admin':
        raise CommandError('Only a fully validated administrator seed may be applied.')
    as_date = lambda value: date.fromisoformat(value) if value else None
    users = get_user_model().objects.in_bulk()
    keys = [r.import_key for r in preview.projects]
    existing = {p.import_key: p for p in Project.objects.select_for_update().filter(import_key__in=keys)}
    old_ids = {p.id for p in existing.values()}
    new, changed = [], []
    for row in preview.projects:
        p = existing.get(row.import_key) or Project(import_key=row.import_key)
        if p.pk and p.project_type != row.project_type:
            raise CommandError('Project type changed after validation.')
        p.name, p.portfolio, p.description = row.name, row.portfolio, row.description
        p.project_type, p.status, p.due_date = row.project_type, row.project_status, as_date(row.due_date)
        p.assigned_user_id, p.research_centre_id = row.manager_id, row.centre_id
        p.created_by_id = p.created_by_id or row.manager_id
        (changed if p.pk else new).append(p)
    Project.objects.bulk_create(new)
    if changed:
        Project.objects.bulk_update(changed, ['name','portfolio','description','project_type','status','due_date','assigned_user','research_centre','created_by'])
    projects = {p.import_key: p for p in new + changed}
    ids = [p.id for p in projects.values()]
    # Match the workbook service's publication fields without per-row signal/read round trips.
    for model, kind in [(Paper, 'paper'), (Book, 'book')]:
        old = {p.project_id: p for p in model.objects.filter(project_id__in=ids)}
        additions, updates, authors = [], [], []
        for row in preview.projects:
            if row.project_type != kind:
                continue
            project = projects[row.import_key]
            p = old.get(project.id) or model(project_id=project.id)
            p.title, p.status, p.lead_author_user_id = row.name, row.publication_status, row.lead_author_id
            lead = users.get(row.lead_author_id)
            p.lead_author = (lead.get_full_name() or lead.username) if lead else ''
            p.created_by_id = p.created_by_id or row.lead_author_id or row.manager_id or actor.id
            p.external_authors = list(row.external_authors)
            if kind == 'paper':
                for field in ['paper_type','internal_external','version','abstract','target_journal']:
                    setattr(p, field, getattr(row, field))
                p.submission_date, p.decision_date = as_date(row.submission_date), as_date(row.decision_date)
                p.updated_at = timezone.now()
            else:
                p.description, p.due_date, p.publisher = row.description, as_date(row.due_date), row.publisher
                p.total_chapters, p.completed_chapters = row.total_chapters, row.completed_chapters
            (updates if p.pk else additions).append(p)
            authors.append((p, row.co_author_ids))
        model.objects.bulk_create(additions)
        fields = ['title','status','lead_author_user','lead_author','created_by','external_authors']
        fields += ['paper_type','internal_external','version','abstract','target_journal','submission_date','decision_date','updated_at'] if kind == 'paper' else ['description','due_date','publisher','total_chapters','completed_chapters']
        if updates:
            model.objects.bulk_update(updates, fields)
        through = model.co_authors_users.through
        model_field = kind + '_id'
        if updates:
            through.objects.filter(**{kind+'__in': updates}).delete()
        through.objects.bulk_create([through(**{model_field: p.pk, 'customuser_id': uid}) for p,uids in authors for uid in uids])
    old_tasks = {(t.project_id,t.import_key):t for t in Task.objects.filter(project_id__in=ids)}
    added_tasks, changed_tasks, saved = [], [], {}
    for row in preview.tasks:
        pid = projects[row.project_import_key].id
        task = old_tasks.get((pid,row.import_key)) or Task(project_id=pid,import_key=row.import_key)
        task.title, task.assigned_to_id = row.title, row.assigned_to_id
        task.status, task.progress = row.status, Task.STATUS_TO_PROGRESS[row.status]
        task.priority, task.task_type = row.priority or None, row.task_type or None
        task.due_date, task.comments = as_date(row.due_date), row.comments
        task.created_by_id = task.created_by_id or actor.id
        task.parent_task_id = None
        (changed_tasks if task.pk else added_tasks).append(task)
        saved[(row.project_import_key,row.normalized_name)] = task
    Task.objects.bulk_create(added_tasks)
    if changed_tasks:
        Task.objects.bulk_update(changed_tasks,['title','assigned_to','status','progress','priority','task_type','due_date','comments','created_by','parent_task'])
    parents = []
    for row in preview.tasks:
        if row.parent_normalized:
            task = saved[(row.project_import_key,row.normalized_name)]
            task.parent_task_id = saved[(row.project_import_key,row.parent_normalized)].pk
            parents.append(task)
    if parents:
        Task.objects.bulk_update(parents,['parent_task'])
    memberships = set()
    for row in preview.projects:
        for uid in set(row.team_user_ids) | set(row.co_author_ids) | set(row.reviewer_ids) | ({row.lead_author_id} if row.lead_author_id else set()):
            memberships.add((projects[row.import_key].id,uid))
    for row in preview.tasks:
        if row.assigned_to_id:
            memberships.add((projects[row.project_import_key].id,row.assigned_to_id))
    members = {m.user_id:m for m in TeamMember.objects.filter(user_id__in={uid for _,uid in memberships})}
    missing = [TeamMember(user_id=uid,full_name=users[uid].get_full_name() or users[uid].username,role=users[uid].get_role_display()) for uid in {uid for _,uid in memberships} - set(members)]
    TeamMember.objects.bulk_create(missing)
    members.update({m.user_id:m for m in missing})
    Assignment.objects.bulk_create([Assignment(project_id=pid,team_member_id=members[uid].id,responsibility='2026 source allocation') for pid,uid in memberships],ignore_conflicts=True)
    return ImportResult(len(new),len(changed),len(added_tasks),len(changed_tasks),tuple(ids),())
