# Kanban, Project Imports, and Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver consistent assignment-aware Kanban and daily work, publication-backed projects, validated bulk imports, and working per-user notifications without risking production data.

**Architecture:** Centralize project/task authorization in focused services, keep new database relationships nullable for legacy compatibility, and drive every role-specific page from the same query rules. Use transactional domain services for linked publication/project and daily/Kanban changes, management commands for imports, and per-user notification receipts.

**Tech Stack:** Django 5.2.4, Python 3.12, Django templates, Bootstrap, vanilla JavaScript, PostgreSQL in production, file-backed SQLite for integration verification.

**Spec:** `docs/superpowers/specs/2026-10-13-kanban-project-imports-notifications-design.md`

## Global Constraints

- Do not modify or discard the existing uncommitted `project_manage/settings.py` proxy/CSRF change.
- New publication, daily-task, and import-identity relationships must be nullable for legacy compatibility.
- Missing related records must render fallback text and must not crash a page.
- New administrator UI copy and project-detail UI must contain no emojis.
- Core workflows must not depend on email delivery or a background queue.
- Production deployment and production imports are not authorized by this plan.
- Every behavior change follows red-green-refactor and the full existing Django suite runs before completion.

## Review Focus

- A task visible only through `Project.assigned_user` must appear consistently in all authorized boards and the daily pool; pin this in Task 2.
- A publication whose creator or linked project is null must still render and backfill safely; pin this in Task 5.
- A repeated import containing a bad row must not duplicate prior rows or leave an orphaned publication project; pin this in Task 6.
- A role/all notification must be readable by one user without becoming read for another; pin this in Task 7.
- Two users updating different tasks while an admin board is open must be reflected after refresh without overwriting either task; pin this in Task 3.

---

## File Structure

- `projects/work_scope.py`: canonical assigned-project/task queries and authorization predicates.
- `projects/daily_work.py`: atomic daily-item/Kanban synchronization.
- `manager/publication_projects.py`: publication-to-project creation, synchronization, and status mapping.
- `adminpanel/notification_service.py`: active audience queries and per-user read state.
- `projects/importing/`: shared CSV parsing, validation, and import result types.
- App-specific management commands: thin adapters from CSV rows to domain services.
- Role-specific views/templates remain in their existing apps, but consume the shared services.

### Task 1: Isolated File-Backed Test Database

**Files:**
- Modify: `project_manage/settings_test.py`
- Modify: `.gitignore`
- Create: `project_manage/test_database_isolation.py`

**Interfaces:**
- Produces: `TEST_DB_PATH` pointing to `test_artifacts/test.db`; Django test configuration that cannot resolve to the production database.

- [ ] **Step 1: Write the failing isolation test**

Add `TestDatabaseIsolationTests.test_test_settings_use_workspace_test_db` asserting SQLite, filename `test.db`, path under `test_artifacts`, and no production database URL dependency.

- [ ] **Step 2: Run the test and verify RED**

Run: `.venv\Scripts\python.exe manage.py test project_manage.test_database_isolation --settings=project_manage.settings_test -v 2`

Expected: FAIL because the configured database is `:memory:`.

- [ ] **Step 3: Implement the isolated setting**

Set `TEST_DB_PATH: pathlib.Path`, configure SQLite `NAME` to that path, retain `ATOMIC_REQUESTS`, and ignore `test_artifacts/` in Git.

- [ ] **Step 4: Run the test and verify GREEN**

Run the Task 1 command; expect PASS and no connection to PostgreSQL.

- [ ] **Step 5: Commit**

Commit `test: isolate Django integration database` with only Task 1 files.

### Task 2: Canonical Assignment and Task Scope

**Files:**
- Create: `projects/work_scope.py`
- Modify: `projects/scope.py`
- Modify: `projects/views.py`
- Modify: `manager/views.py`
- Modify: `adminpanel/views.py`
- Create: `projects/test_work_scope.py`
- Modify: `projects/test_role_kanban_permissions.py`

**Interfaces:**
- Produces: `assigned_projects_for(user, queryset=None) -> QuerySet[Project]`, `workable_tasks_for(user, queryset=None) -> QuerySet[Task]`, `can_update_task(user, task) -> bool`, and `inspectable_users_for(user) -> QuerySet[CustomUser]`.
- Consumes: existing research-centre constraints from `projects.scope.scope_projects_for_user`.

- [ ] **Step 1: Write failing scope tests**

Test direct project assignment, direct task assignment, team membership, admin assignment, centre-head isolation, unrelated-task exclusion, and a task reachable only through `Project.assigned_user`.

- [ ] **Step 2: Verify RED**

Run: `.venv\Scripts\python.exe manage.py test projects.test_work_scope --settings=project_manage.settings_test -v 2`

Expected: FAIL because `projects.work_scope` does not exist.

- [ ] **Step 3: Implement the shared query functions**

Use composable `Q` objects, `distinct()`, existing institutional/centre scoping, and no role-based shortcut that exposes unrelated tasks.

- [ ] **Step 4: Replace duplicated board query logic**

Update staff, manager, and admin viewer views to consume the new functions while preserving each role's edit restrictions.

- [ ] **Step 5: Verify GREEN and regressions**

Run Task 2 tests plus `projects.test_role_kanban_permissions` and `projects.test_staff_kanban`; expect PASS.

- [ ] **Step 6: Commit**

Commit `fix: unify project and task assignment scope`.

### Task 3: Administrator My Projects and Detailed Staff Viewer

**Files:**
- Modify: `adminpanel/urls.py`
- Modify: `adminpanel/views.py`
- Modify: `templates/adminpanel/index.html`
- Modify: `templates/adminpanel/admin_kanban.html`
- Modify: `templates/adminpanel/partials/user_kanban.html`
- Create: `templates/adminpanel/my_projects.html`
- Create: `adminpanel/test_admin_kanban_workflow.py`

**Interfaces:**
- Consumes: `assigned_projects_for`, `workable_tasks_for`, `can_update_task`, `inspectable_users_for` from Task 2.
- Produces: named routes `admin_my_projects`, `admin_my_task_update`, and the corrected `admin_user_kanban`; partial HTML includes `data-last-updated`.

- [ ] **Step 1: Write failing admin workflow tests**

Assert that an assigned admin sees My Projects, can update only authorized task status/comments, cannot change ownership, sees admin users in the permitted filter, and receives 403 for another user's task.

- [ ] **Step 2: Write failing detail/refresh tests**

Assert complete project/task table labels, fallback values, overdue/due-today/due-within-seven-days classes, no emoji characters in new templates, a changing `data-last-updated`, and a refreshed response showing another client's committed update.

- [ ] **Step 3: Verify RED**

Run: `.venv\Scripts\python.exe manage.py test adminpanel.test_admin_kanban_workflow --settings=project_manage.settings_test -v 2`

- [ ] **Step 4: Implement routes, views, and My Projects page**

Use POST-only updates, explicit valid-status checks, `update_fields`, and server-side authorization from Task 2.

- [ ] **Step 5: Implement the staff-detail modal and safe refresh**

Render a compact Bootstrap modal with a table and text alerts. Poll the selected partial every 30 seconds only while visible; add a manual refresh button; require `response.ok` before inserting returned HTML.

- [ ] **Step 6: Verify GREEN**

Run Task 3 tests and Task 2 regression tests; expect PASS.

- [ ] **Step 7: Commit**

Commit `feat: add admin assigned-work board and detailed staff viewer`.

### Task 4: Assigned-Pool Daily Work

**Files:**
- Modify: `projects/models.py`
- Create: `projects/migrations/0009_dailytask_assigned_work.py`
- Create: `projects/daily_work.py`
- Modify: `projects/forms.py`
- Modify: `projects/views.py`
- Modify: `projects/urls.py`
- Modify: `templates/projects/dashboard.html`
- Create: `projects/test_daily_work.py`

**Interfaces:**
- Consumes: `workable_tasks_for` and `can_update_task` from Task 2.
- Produces: `complete_daily_work(item, user) -> DailyTask`, `reopen_daily_work(item, user) -> DailyTask`; URL names `daily_task_complete`, `daily_task_reopen`, and `daily_task_delete`.

- [ ] **Step 1: Write failing model/form tests**

Assert nullable legacy link, indexed `work_date`, nullable `completed_at`, same-day duplicate prevention for a non-null task, assigned-only choices, and rejection of arbitrary/unassigned task IDs.

- [ ] **Step 2: Write failing synchronization tests**

Assert atomic completion sets daily state and Kanban `done`/100%, reopening sets `in_progress`/33%, legacy null-linked items remain operable, and deleting a Task sets the daily link null.

- [ ] **Step 3: Write the endpoint-collision regression test**

Assert daily deletion reaches its own view while Kanban deletion remains forbidden to staff.

- [ ] **Step 4: Verify RED**

Run: `.venv\Scripts\python.exe manage.py test projects.test_daily_work --settings=project_manage.settings_test -v 2`

- [ ] **Step 5: Add the migration, domain service, forms, and distinct endpoints**

Keep legacy `title`; populate it from the chosen task on new rows. Use `transaction.atomic()` and row locking in completion/reopen operations.

- [ ] **Step 6: Replace free-text dashboard creation with assigned-task/date selection**

Render safe legacy rows, day navigation, assigned pool, completion/reopen actions, and empty states.

- [ ] **Step 7: Verify GREEN**

Run Task 4 tests plus existing `projects.tests` and Kanban tests; expect PASS.

- [ ] **Step 8: Commit**

Commit `feat: derive daily work from assigned project tasks`.

### Task 5: Publication-to-Project Links and Backfill

**Files:**
- Modify: `projects/models.py`
- Create: `projects/migrations/0010_project_import_identity.py`
- Modify: `manager/models.py`
- Create: `manager/migrations/0009_publication_project_links.py`
- Create: `manager/migrations/0010_backfill_publication_projects.py`
- Create: `manager/publication_projects.py`
- Modify: `manager/views.py`
- Modify: `adminpanel/views.py`
- Modify: publication templates under `templates/manager/` and `templates/adminpanel/`
- Create: `manager/test_publication_projects.py`

**Interfaces:**
- Produces: `sync_publication_project(publication, *, actor, manager=None, research_centre=None) -> Project` and status maps for `Book`, `Paper`, and `Conference`.
- Produces nullable unique `Project.import_key`; nullable `Project.created_by`; nullable one-to-one `project` fields on each publication model.

- [ ] **Step 1: Write failing model/service tests**

Assert atomic project creation, one-to-one links, `conference` project type, deterministic status mapping, updates without duplicate projects, and null-safe rendering.

- [ ] **Step 2: Write failing backfill tests**

Use `MigrationExecutor` to cover records with a creator, records with null creators, duplicate titles, already-linked rows, and a failed/partial legacy relationship. Assert every viable publication receives at most one project and page loads never depend on a link.

- [ ] **Step 3: Verify RED**

Run: `.venv\Scripts\python.exe manage.py test manager.test_publication_projects --settings=project_manage.settings_test -v 2`

- [ ] **Step 4: Add schema migrations and synchronization service**

Use `transaction.atomic()`. Map terminal published/presented states to `completed`, rejected states to `on-hold`, drafts to `planning`, and active publication states to `in-progress`.

- [ ] **Step 5: Route publication create/update flows through the service**

Keep publication-specific fields in their models and render `Project setup pending` when the link is absent.

- [ ] **Step 6: Implement and verify the backfill migration**

Generate deterministic import keys and names; allow a null project creator when no legacy user can be resolved.

- [ ] **Step 7: Verify GREEN**

Run Task 5 tests and all existing manager/adminpanel model tests; expect PASS.

- [ ] **Step 8: Commit**

Commit `feat: link publications to project workflows`.

### Task 6: Validated Idempotent Bulk Imports and Templates

**Files:**
- Create: `projects/importing/__init__.py`
- Create: `projects/importing/csv_tools.py`
- Create: `projects/management/__init__.py`
- Create: `projects/management/commands/__init__.py`
- Create: `projects/management/commands/import_projects.py`
- Create: `manager/management/commands/import_publications.py`
- Create: `projects/test_project_imports.py`
- Create: `manager/test_publication_imports.py`
- Create/modify: CSV files under `outputs/import_templates/`
- Create: `outputs/import_templates/README.md`

**Interfaces:**
- Produces: `ImportIssue(row_number: int, field: str, message: str)`, `ImportSummary(created, updated, skipped, failed)`, normalized username-list parsing, and commands with `--dry-run`.
- Consumes: `sync_publication_project` from Task 5 and the existing `seed_users_from_csv` command.

- [ ] **Step 1: Write failing parser and project-import tests**

Assert UTF-8 BOM handling, required headers, username lookup, semicolon lists, exact choices, date validation, cross-centre rejection, dry-run no writes, stable `import_key`, and idempotent updates.

- [ ] **Step 2: Write failing publication-import tests**

Cover books, papers, and conferences; project manager, lead author, co-authors, reviewers, team members; bad-row rollback; duplicate keys; missing files; and no orphaned project after a failed row.

- [ ] **Step 3: Verify RED**

Run the two Task 6 test modules; expect FAIL because import modules/commands do not exist.

- [ ] **Step 4: Implement shared CSV validation and project command**

Validate the whole batch before live writes. Use atomic row writes and return row-numbered errors and summary counts.

- [ ] **Step 5: Implement publication command through Task 5 service**

Use a required `kind` column with exact values `book`, `paper`, or `conference`; never create publication/project pairs outside one atomic transaction.

- [ ] **Step 6: Add seedable templates and acceptable-value documentation**

Provide separate users, projects, books, papers, and conferences CSVs using usernames and documented semicolon fields; remove any real passwords or production secrets.

- [ ] **Step 7: Verify GREEN**

Run Task 6 tests plus `users.test_seed_users_command`; expect PASS.

- [ ] **Step 8: Commit**

Commit `feat: add validated project and publication imports`.

### Task 7: Per-User Notification Delivery and Read State

**Files:**
- Modify: `adminpanel/models.py`
- Create: `adminpanel/migrations/0027_notificationreceipt.py`
- Create: `adminpanel/notification_service.py`
- Modify: `adminpanel/notification_views.py`
- Modify: `adminpanel/views.py`
- Modify: `templates/adminpanel/index.html`
- Modify: `templates/adminpanel/overview.html`
- Modify: `templates/adminpanel/partials/notifications_widget.html`
- Modify: `templates/projects/dashboard.html`
- Modify: `templates/manager/manager_dashboard.html`
- Create: `adminpanel/test_notifications.py`

**Interfaces:**
- Produces: `visible_notifications_for(user, *, period=None, at=None) -> QuerySet[Notification]`, `unread_count_for(user, *, at=None) -> int`, and `mark_read(user, notification) -> NotificationReceipt`.

- [ ] **Step 1: Write failing audience/read tests**

Assert `all`, matching role, specific recipient, nonmatching role exclusion, scheduled/expired exclusion, independent read state for two users, inaccessible mark-read 404/403, and pinned state independent from unread state.

- [ ] **Step 2: Write failing page/API tests**

Assert API payload/read count, overview recipient filtering, Today/Week/Month results, widget inclusion, escaped notification body, and no dependency on a CSRF input existing elsewhere in the page.

- [ ] **Step 3: Verify RED**

Run: `.venv\Scripts\python.exe manage.py test adminpanel.test_notifications --settings=project_manage.settings_test -v 2`

- [ ] **Step 4: Add receipt migration and notification service**

Use a unique notification/user constraint and `read_at`; keep global notification rows immutable when one user reads them.

- [ ] **Step 5: Replace divergent page/API queries and repair widget behavior**

Use the service everywhere, real period query parameters, cookie-based CSRF lookup, DOM text assignment for untrusted fields, and explicit error states.

- [ ] **Step 6: Verify GREEN**

Run Task 7 tests plus existing assignment-notification tests; expect PASS.

- [ ] **Step 7: Commit**

Commit `fix: make notifications audience-aware and readable per user`.

### Task 8: System Audit, Migrations, and Integrated `test.db` Verification

**Files:**
- Modify: `README.md`
- Create: `docs/testing/kanban-import-notification-audit.md`
- Modify: tests only if the full run exposes a confirmed regression; production fixes require a new red-green cycle.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: reproducible setup/import/test commands and an evidence-backed audit report.

- [ ] **Step 1: Run static Django checks and migration consistency**

Run: `.venv\Scripts\python.exe manage.py check --settings=project_manage.settings_test`

Run: `.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=project_manage.settings_test`

Expected: no issues and no missing migrations.

- [ ] **Step 2: Recreate and migrate isolated `test.db`**

Delete only the resolved `test_artifacts/test.db`, verify the resolved path remains under the workspace test-artifact directory, then run migrations with test settings.

- [ ] **Step 3: Exercise dry-run and live seed workflows on `test.db`**

Run user/project/publication template dry-runs, seed representative records, rerun the same files, and verify idempotent summary counts.

- [ ] **Step 4: Run focused integration tests**

Run Tasks 2-7 test modules together with `--keepdb`; expect PASS.

- [ ] **Step 5: Run the complete suite**

Run: `.venv\Scripts\python.exe manage.py test --settings=project_manage.settings_test -v 2`

Expected: all tests PASS. Record any pre-existing failure by full test name; do not hide it.

- [ ] **Step 6: Perform browser smoke tests**

With representative admin, manager, and staff accounts in `test.db`, verify admin My Projects updates, staff-filter refresh/modal/alerts, daily completion synchronization, notification read state, and missing-link fallback pages.

- [ ] **Step 7: Document results and production runbook**

Record commands, counts, known limitations, rollback-safe migration sequence, dry-run requirement, and the explicit statement that production deployment/import requires separate approval.

- [ ] **Step 8: Run final diff and secret checks**

Run `git diff --check`, confirm no database, credentials, or real passwords are tracked, and inspect `git status --short` to ensure the user's settings change remains intact.

- [ ] **Step 9: Commit**

Commit `docs: add verified rollout and audit runbook`.
