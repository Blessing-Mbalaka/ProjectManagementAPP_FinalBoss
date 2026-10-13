# Kanban, imports, daily work, and notification audit

Audit date: 2026-10-13

## Outcome

The approved changes are implemented and verified against an isolated, file-backed SQLite database at `test_artifacts/test.db`. No production database, deployment, or real user account was changed.

The audit covers:

- consistent assignment scope for admin, manager, and staff Kanban pages;
- an admin `My Projects` board, including work assigned to an admin who is not the project manager;
- an admin staff filter with a detailed project/task table modal and overdue/due-soon indicators;
- persistent daily work selected only from the signed-in user's assigned project task pool;
- nullable legacy daily-task links and safe missing-project/publication fallbacks;
- books, papers, and conferences linked one-to-one to normal projects;
- validated, idempotent CSV imports for users, projects, books, papers, and conferences;
- active-window and audience-aware notifications with independent per-user read receipts;
- a notification bell on admin, manager, and staff base layouts.

## Why admin Kanban updates were not visible

Role pages previously assembled project/task visibility independently. This produced different assignment rules and stale or incomplete staff-filter results. The repair centralizes assigned-project, workable-task, update-permission, and inspectable-user queries in `projects/work_scope.py`. Admin filtered results now use the same canonical scope as the update endpoint, and the partial includes a last-updated marker. The admin page refreshes on demand and every 30 seconds.

## Concurrency and capacity

The update paths use normal transactional database writes and authorization checks. A background queue is not required for 23 interactive users: Kanban changes, daily completion, and notification reads are short request/response transactions. Production should use PostgreSQL with its normal connection management. A queue would become useful only for slow external work such as bulk email delivery, large report generation, or very large imports.

Imports validate the complete CSV before writing rows and then write each valid row atomically. Stable `import_key` values make reruns updates rather than duplicates. For production, run one controlled import process at a time to keep operator summaries easy to reconcile.

## Verified commands and results

Static and migration checks:

```powershell
.\.venv\Scripts\python.exe manage.py check --settings=project_manage.settings_test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=project_manage.settings_test
.\.venv\Scripts\python.exe manage.py migrate --settings=project_manage.settings_test --noinput
```

Result: Django reported no system-check issues or missing migrations. All migrations through `adminpanel.0027`, `projects.0011`, and `manager.0010` applied successfully to a newly created `test.db`.

Template workflow:

1. Created the example research centre in `test.db`.
2. User dry-run validated six rows.
3. After users existed, project and all three publication dry-runs each validated one row with no writes.
4. Live import created six users, one ordinary project, and one linked project for each book, paper, and conference.
5. Repeating the same files created zero users and updated the four existing project identities; final counts remained four projects and one record of each publication kind.

Automated verification:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=project_manage.settings_test --noinput
```

Result: 108 tests passed. This includes route/template-level Django client tests for the admin staff modal, admin My Projects updates, staff/manager authorization, persistent daily work synchronization, missing-link fallbacks, notification audience/read behavior, and import idempotency.

The test runner intentionally discovers Django application tests rather than importing three root-level diagnostic scripts whose filenames start with `test_` but execute database queries at import time. Those scripts remain available for manual diagnostics and are not part of the unit/integration suite.

## Import order

1. Back up the production database.
2. Deploy application code.
3. Run `python manage.py check` and `python manage.py migrate --plan`.
4. Apply migrations with `python manage.py migrate`.
5. Confirm the required research centres exist.
6. Dry-run and then import users by research centre.
7. Dry-run and then import ordinary projects.
8. Dry-run and then import books, papers, and conferences.
9. Verify admin My Projects, staff-filter Kanban, daily work, and notifications with representative accounts.

Do not run a production import without a clean dry-run. Do not use real passwords in tracked CSV files. The included credentials are placeholders and must be replaced through a secure operational process.

## Rollback

Before production migration, take a database backup. If application verification fails, stop new writes, restore the prior application release, and restore the database backup when a schema/data rollback is required. The import commands do not provide destructive rollback; their stable keys support correction and rerun, but deletion of an imported batch must be reviewed and performed explicitly.

## Known operational limits

- Notification polling is every 30 seconds, so cross-user updates are near-real-time rather than WebSocket real-time.
- Bulk email is intentionally not queued by this work.
- CSV imports are suited to controlled administrative batches, not simultaneous uploads by many operators.
- `test.db` is ignored by Git and is not a production database artifact.
