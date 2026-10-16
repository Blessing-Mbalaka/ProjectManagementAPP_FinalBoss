import hashlib
from dataclasses import asdict, dataclass
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.db.models import Q

from adminpanel.models import ResearchCentre
from manager.models import Book, Conference, Paper
from projects.models import Project, Task
from projects.scope import scope_projects_for_user


User = get_user_model()
AUTHOR_FIELDS = ("lead_author_username", "co_author_usernames")
PUBLICATION_FIELDS = (
    "publication_status", "lead_author_username", "co_author_usernames",
    "external_authors", "reviewer_usernames", "publisher", "total_chapters",
    "completed_chapters", "internal_external", "paper_type", "version",
    "abstract", "target_journal", "conference_name", "conference_date",
    "location", "submission_date", "decision_date",
)


@dataclass(frozen=True)
class ImportIssue:
    level: str
    sheet: str
    row: int | None
    field: str
    message: str


@dataclass(frozen=True)
class ImportAction:
    category: str
    operation: str
    label: str
    details: str = ""


@dataclass(frozen=True)
class ProjectRow:
    row: int
    import_key: str
    name: str
    portfolio: str | None
    description: str
    project_type: str
    project_status: str
    due_date: str | None
    manager_id: int | None
    centre_id: int | None
    team_user_ids: tuple[int, ...]
    publication_status: str
    lead_author_id: int | None
    co_author_ids: tuple[int, ...]
    external_authors: tuple[str, ...]
    reviewer_ids: tuple[int, ...]
    publisher: str
    total_chapters: int
    completed_chapters: int
    internal_external: str
    paper_type: str
    version: str
    abstract: str
    target_journal: str
    conference_name: str
    conference_date: str | None
    location: str
    submission_date: str | None
    decision_date: str | None
    existing_project_id: int | None


@dataclass(frozen=True)
class TaskRow:
    row: int
    project_import_key: str
    project_name: str
    title: str
    normalized_name: str
    import_key: str
    parent_name: str
    parent_normalized: str
    assigned_to_id: int | None
    responsibility: str
    status: str
    priority: str
    task_type: str
    due_date: str | None
    comments: str
    existing_task_id: int | None


@dataclass(frozen=True)
class WorkbookImportPreview:
    actor_id: int
    projects: tuple[ProjectRow, ...]
    tasks: tuple[TaskRow, ...]
    issues: tuple[ImportIssue, ...]
    actions: tuple[ImportAction, ...]

    @property
    def errors(self):
        return tuple(issue for issue in self.issues if issue.level == "error")

    @property
    def warnings(self):
        return tuple(issue for issue in self.issues if issue.level == "warning")

    @property
    def is_valid(self):
        return not self.errors

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            actor_id=data["actor_id"],
            projects=tuple(ProjectRow(**row) for row in data["projects"]),
            tasks=tuple(TaskRow(**row) for row in data["tasks"]),
            issues=tuple(ImportIssue(**row) for row in data["issues"]),
            actions=tuple(ImportAction(**row) for row in data["actions"]),
        )


def normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def task_import_key(title: str) -> str:
    digest = hashlib.sha256(normalize_name(title).encode("utf-8")).hexdigest()[:32]
    return f"task:{digest}"


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _choice_value(value, choices):
    text = _text(value)
    canonical = {normalize_name(stored): stored for stored, _label in choices}
    return canonical.get(normalize_name(text), text)


def _split(value):
    return tuple(item.strip() for item in _text(value).split(";") if item.strip())


def _external_names(value):
    result = []
    seen = set()
    for name in _split(value):
        key = normalize_name(name)
        if key not in seen:
            seen.add(key)
            result.append(name)
    return tuple(result)


def _date_value(value, issue, *, field):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _text(value)
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        issue(field, f"{field} must use YYYY-MM-DD.")
        return None


def _can_manage_existing(actor, project):
    if actor.role in {"admin", "dean"}:
        return True
    if actor.role == "centrehead":
        return bool(actor.research_centre_id and actor.research_centre_id == project.research_centre_id)
    return project.created_by_id == actor.id or project.assigned_user_id == actor.id


def validate_workbook(read_result, *, actor) -> WorkbookImportPreview:
    issues = [
        ImportIssue("error", error.sheet, error.row, error.field, error.message)
        for error in read_result.errors
    ]
    actions = []
    projects = []
    tasks = []
    project_names = {}
    import_keys = set()
    project_context = {}

    def add_issue(level, sheet, row, field, message):
        issues.append(ImportIssue(level, sheet, row, field, message))

    for raw in read_result.project_rows:
        row_number = int(raw.get("_row") or 0)

        def project_issue(field, message, level="error"):
            add_issue(level, "Projects", row_number, field, message)

        values = {key: _text(raw.get(key)) for key in raw if key != "_row"}
        import_key = values.get("import_key", "")
        name = values.get("project_name", "")
        project_type = _choice_value(values.get("project_type"), Project.PROJECT_TYPES)
        project_status = _choice_value(values.get("project_status"), Project.STATUS_CHOICES)
        normalized_name = normalize_name(name)

        for field in ("import_key", "project_name", "project_type", "project_status", "project_manager_username", "research_centre"):
            if not values.get(field):
                project_issue(field, f"{field} is required.")
        if import_key in import_keys:
            project_issue("import_key", f'Duplicate import_key "{import_key}".')
        import_keys.add(import_key)
        if normalized_name in project_names:
            project_issue("project_name", f'Project name "{name}" duplicates another row after whitespace/case normalization.')
        else:
            project_names[normalized_name] = import_key

        valid_project_types = {choice for choice, _ in Project.PROJECT_TYPES}
        valid_project_statuses = {choice for choice, _ in Project.STATUS_CHOICES}
        if project_type and project_type not in valid_project_types:
            project_issue("project_type", f'Invalid project_type "{project_type}".')
        if project_status and project_status not in valid_project_statuses:
            project_issue("project_status", f'Invalid project_status "{project_status}".')

        manager = User.objects.filter(username=values.get("project_manager_username", "")).first()
        if values.get("project_manager_username") and manager is None:
            project_issue("project_manager_username", f'Username "{values["project_manager_username"]}" was not found.')
        centre = ResearchCentre.objects.filter(name=values.get("research_centre", "")).first()
        if values.get("research_centre") and centre is None:
            project_issue("research_centre", f'Research centre "{values["research_centre"]}" was not found.')
        if manager and centre and manager.research_centre_id not in (None, centre.id):
            project_issue("project_manager_username", f'Username "{manager.username}" belongs to another research centre.')
        if centre and actor.role not in {"admin", "dean"} and actor.research_centre_id != centre.id:
            project_issue("research_centre", "You may only import projects for your own research centre.")

        existing = Project.objects.filter(import_key=import_key).first() if import_key else None
        if existing and not _can_manage_existing(actor, existing):
            project_issue("import_key", f'You are not authorized to update project "{existing.name}".')
        if existing and project_type and existing.project_type != project_type:
            project_issue("project_type", "An existing project's type cannot be changed by workbook import.")
        if existing and not scope_projects_for_user(Project.objects.filter(pk=existing.pk), actor).exists():
            project_issue("import_key", f'Project "{existing.name}" is outside your project scope.')

        team_ids = []
        for username in _split(values.get("team_usernames")):
            user = User.objects.filter(username=username).first()
            if not user:
                project_issue("team_usernames", f'Username "{username}" was not found.')
            elif centre and user.research_centre_id not in (None, centre.id):
                project_issue("team_usernames", f'Username "{username}" belongs to another research centre.')
            else:
                team_ids.append(user.id)

        def author_ids(field):
            found = []
            for username in _split(values.get(field)):
                user = User.objects.filter(username=username).first()
                if not user:
                    project_issue(field, f'Author username "{username}" was not found and will be skipped.', "warning")
                elif centre and user.research_centre_id not in (None, centre.id):
                    project_issue(field, f'Author username "{username}" belongs to another research centre and will be skipped.', "warning")
                else:
                    found.append(user.id)
            return tuple(dict.fromkeys(found))

        lead_ids = author_ids("lead_author_username")
        co_author_ids = author_ids("co_author_usernames")
        external_authors = _external_names(values.get("external_authors"))
        reviewer_ids = []
        for username in _split(values.get("reviewer_usernames")):
            user = User.objects.filter(username=username).first()
            if not user:
                project_issue("reviewer_usernames", f'Reviewer username "{username}" was not found.')
            elif centre and user.research_centre_id not in (None, centre.id):
                project_issue("reviewer_usernames", f'Reviewer username "{username}" belongs to another research centre.')
            else:
                reviewer_ids.append(user.id)

        due_date = _date_value(raw.get("due_date"), project_issue, field="due_date")
        conference_date = _date_value(raw.get("conference_date"), project_issue, field="conference_date")
        submission_date = _date_value(raw.get("submission_date"), project_issue, field="submission_date")
        decision_date = _date_value(raw.get("decision_date"), project_issue, field="decision_date")

        publication_model = {"book": Book, "paper": Paper, "conference": Conference}.get(project_type)
        publication_status = _choice_value(
            values.get("publication_status"),
            publication_model.STATUS_CHOICES if publication_model else (),
        )
        internal_external = _choice_value(
            values.get("internal_external"),
            (("internal", "Internal"), ("external", "External")),
        )
        paper_type = _choice_value(values.get("paper_type"), Paper.PAPER_TYPE_CHOICES)
        total_chapters = 1
        completed_chapters = 0
        if project_type == "software":
            for field in PUBLICATION_FIELDS:
                if values.get(field):
                    project_issue(field, f"{field} is not valid for a software project.")
        elif project_type in {"book", "paper", "conference"}:
            model = {"book": Book, "paper": Paper, "conference": Conference}[project_type]
            valid_statuses = {choice for choice, _ in model.STATUS_CHOICES}
            if not publication_status:
                project_issue("publication_status", "publication_status is required for publication projects.")
            elif publication_status not in valid_statuses:
                project_issue("publication_status", f'Invalid {project_type} status "{publication_status}".')
            if existing:
                linked_kinds = [kind for kind in ("book", "paper", "conference") if hasattr(existing, f"{kind}_publication")]
                if linked_kinds and project_type not in linked_kinds:
                    project_issue("project_type", f'Project is already linked to a {linked_kinds[0]} publication.')
            if project_type == "book":
                try:
                    total_chapters = int(values.get("total_chapters") or 1)
                    completed_chapters = int(values.get("completed_chapters") or 0)
                    if total_chapters < 1:
                        project_issue("total_chapters", "total_chapters must be at least 1.")
                    if completed_chapters < 0 or completed_chapters > total_chapters:
                        project_issue("completed_chapters", "completed_chapters must be between 0 and total_chapters.")
                except ValueError:
                    project_issue("total_chapters", "Chapter counts must be whole numbers.")
            elif project_type == "paper":
                if internal_external not in {"internal", "external"}:
                    project_issue("internal_external", "internal_external must be internal or external.")
                if paper_type not in {choice for choice, _ in Paper.PAPER_TYPE_CHOICES}:
                    project_issue("paper_type", "paper_type must be journal or conference.")
                if not values.get("version"):
                    project_issue("version", "version is required for paper projects.")
            elif project_type == "conference":
                if internal_external not in {"internal", "external"}:
                    project_issue("internal_external", "internal_external must be internal or external.")
                if not values.get("conference_name"):
                    project_issue("conference_name", "conference_name is required for conference projects.")

        project_row = ProjectRow(
            row=row_number,
            import_key=import_key,
            name=name,
            portfolio=values.get("portfolio") or None,
            description=values.get("description", "")[:255],
            project_type=project_type,
            project_status=project_status,
            due_date=due_date,
            manager_id=manager.id if manager else None,
            centre_id=centre.id if centre else None,
            team_user_ids=tuple(dict.fromkeys(team_ids)),
            publication_status=publication_status,
            lead_author_id=lead_ids[0] if lead_ids else None,
            co_author_ids=co_author_ids,
            external_authors=external_authors,
            reviewer_ids=tuple(dict.fromkeys(reviewer_ids)),
            publisher=values.get("publisher", ""),
            total_chapters=total_chapters,
            completed_chapters=completed_chapters,
            internal_external=internal_external,
            paper_type=paper_type,
            version=values.get("version", ""),
            abstract=values.get("abstract", ""),
            target_journal=values.get("target_journal", ""),
            conference_name=values.get("conference_name", ""),
            conference_date=conference_date,
            location=values.get("location", ""),
            submission_date=submission_date,
            decision_date=decision_date,
            existing_project_id=existing.id if existing else None,
        )
        projects.append(project_row)
        existing_tasks = tuple(existing.tasks.all()) if existing else ()
        project_context[normalized_name] = (project_row, centre, existing, existing_tasks)
        actions.append(ImportAction("project", "update" if existing else "create", name))
        if existing and project_type in {"book", "paper", "conference"}:
            publication = getattr(existing, f"{project_type}_publication", None)
            if publication and tuple(publication.external_authors or []) != external_authors:
                actions.append(ImportAction("publication", "update", f"External authors for {name}"))

    task_seen = {}
    task_rows_by_project = {}
    for raw in read_result.task_rows:
        row_number = int(raw.get("_row") or 0)

        def task_issue(field, message, level="error"):
            add_issue(level, "Tasks", row_number, field, message)

        project_name = _text(raw.get("project_name"))
        title = _text(raw.get("task_name"))
        project_key = normalize_name(project_name)
        normalized_title = normalize_name(title)
        context = project_context.get(project_key)
        if not project_name:
            task_issue("project_name", "project_name is required.")
        elif not context:
            task_issue("project_name", f'Project "{project_name}" was not found in the Projects sheet.')
        if not title:
            task_issue("task_name", "task_name is required.")
        duplicate_key = (project_key, normalized_title)
        if normalized_title and duplicate_key in task_seen:
            task_issue("task_name", f'Task name "{title}" duplicates another row after whitespace/case normalization.')
        task_seen[duplicate_key] = row_number

        assignee = None
        assigned_username = _text(raw.get("assigned_to"))
        centre = context[1] if context else None
        if assigned_username:
            assignee = User.objects.filter(username=assigned_username).first()
            if not assignee:
                task_issue("assigned_to", f'Username "{assigned_username}" was not found.')
            elif centre and assignee.research_centre_id not in (None, centre.id):
                task_issue("assigned_to", f'Username "{assigned_username}" belongs to another research centre.')

        status = _choice_value(raw.get("status"), Task.STATUS_CHOICES) or "todo"
        priority = _choice_value(raw.get("priority"), Task.PRIORITY_CHOICES)
        task_type = _choice_value(raw.get("task_type"), Task.PROJECT_PHASES)
        if status not in {choice for choice, _ in Task.STATUS_CHOICES}:
            task_issue("status", f'Invalid task status "{status}".')
        if priority and priority not in {choice for choice, _ in Task.PRIORITY_CHOICES}:
            task_issue("priority", f'Invalid priority "{priority}".')
        if task_type and task_type not in {choice for choice, _ in Task.PROJECT_PHASES}:
            task_issue("task_type", f'Invalid task_type "{task_type}".')
        due_date = _date_value(raw.get("due_date"), task_issue, field="due_date")

        existing_task = None
        existing_project = context[2] if context else None
        if existing_project and normalized_title:
            matching_tasks = [
                item for item in context[3]
                if normalize_name(item.title) == normalized_title
            ]
            if len(matching_tasks) > 1:
                task_issue(
                    "task_name",
                    f'Task name "{title}" is ambiguous because multiple existing tasks normalize to the same name.',
                )
            elif matching_tasks:
                existing_task = matching_tasks[0]
        task_row = TaskRow(
            row=row_number,
            project_import_key=context[0].import_key if context else "",
            project_name=project_name,
            title=title,
            normalized_name=normalized_title,
            import_key=task_import_key(title),
            parent_name=_text(raw.get("parent_task")),
            parent_normalized=normalize_name(raw.get("parent_task")),
            assigned_to_id=assignee.id if assignee else None,
            responsibility=_text(raw.get("responsibility")) or "Task assignee",
            status=status,
            priority=priority,
            task_type=task_type,
            due_date=due_date,
            comments=_text(raw.get("comments")),
            existing_task_id=existing_task.id if existing_task else None,
        )
        tasks.append(task_row)
        task_rows_by_project.setdefault(project_key, {})[normalized_title] = task_row
        actions.append(ImportAction("task", "update" if existing_task else "create", title, project_name))

        if assignee and context:
            project_row = context[0]
            automatic_ids = set(project_row.team_user_ids) | set(project_row.co_author_ids) | set(project_row.reviewer_ids)
            if project_row.lead_author_id:
                automatic_ids.add(project_row.lead_author_id)
            if assignee.id not in automatic_ids:
                actions.append(ImportAction("membership", "create", assignee.username, project_name))

    all_uploaded_titles = {
        (project_key, title)
        for project_key, title_map in task_rows_by_project.items()
        for title in title_map
    }
    for task in tasks:
        if not task.parent_normalized:
            continue
        project_key = normalize_name(task.project_name)
        if task.parent_normalized == task.normalized_name:
            add_issue("error", "Tasks", task.row, "parent_task", f'Task "{task.title}" cannot be its own parent.')
            continue
        if (project_key, task.parent_normalized) in all_uploaded_titles:
            continue
        context = project_context.get(project_key)
        existing_project = context[2] if context else None
        existing_titles = {
            normalize_name(item.title) for item in context[3]
        } if existing_project else set()
        if task.parent_normalized not in existing_titles:
            other_project = any(
                key != project_key and task.parent_normalized in title_map
                for key, title_map in task_rows_by_project.items()
            )
            reason = "belongs to another project" if other_project else "was not found"
            add_issue("error", "Tasks", task.row, "parent_task", f'Parent task "{task.parent_name}" {reason} for project "{task.project_name}".')

    for project_key, title_map in task_rows_by_project.items():
        visiting = set()
        visited = set()

        def visit(title):
            if title in visited:
                return
            if title in visiting:
                cycle_task = title_map[title]
                add_issue("error", "Tasks", cycle_task.row, "parent_task", f'Task hierarchy contains a cycle at "{cycle_task.title}".')
                return
            visiting.add(title)
            parent = title_map[title].parent_normalized
            if parent in title_map:
                visit(parent)
            visiting.remove(title)
            visited.add(title)

        for title in title_map:
            visit(title)

    return WorkbookImportPreview(
        actor_id=actor.id,
        projects=tuple(projects),
        tasks=tuple(tasks),
        issues=tuple(issues),
        actions=tuple(actions),
    )
