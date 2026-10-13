# Kanban, Project Imports, and Notifications Design

## Purpose

Make project work reliable for administrators, managers, and staff before production deployment. The system must show current Kanban data to administrators, give administrators an editable board for work assigned to them, derive staff daily work from assigned project tasks, support safe bulk onboarding of projects and publication projects, and make notifications behave consistently.

The implementation must remain compatible with existing records. Missing optional relationships must render a useful fallback and must never prevent a page from loading.

## Confirmed Requirements

- Administrators can inspect a selected staff member's current Kanban board.
- The selected staff board is read-only for the inspecting administrator and refreshes to show recent updates.
- Selecting a task opens a small, text-only detail modal. It shows all project and task details in a table and highlights approaching or overdue due dates. No emojis are used.
- Administrators have a separate **My Projects** page for projects assigned to them directly or through a team assignment.
- An administrator may update status and comments on tasks they are authorized to work on even when they are not the project manager.
- Staff daily work is selected only from the pool of Kanban tasks assigned to that staff member directly or through project membership.
- Completing a linked daily item completes the corresponding Kanban task.
- Books, papers, and conferences are publication records linked one-to-one to real project records.
- Current publication records are backfilled safely.
- Bulk imports support users, ordinary projects, books, papers, and conferences.
- Bulk templates identify users by stable username and include all required assignment and publication fields.
- All changes are verified against an isolated file-backed SQLite `test.db` before production deployment.
- The target load is approximately 23 users. No task queue is required for the core workflow.

## Current Root Causes

### Admin Kanban

The admin board currently excludes users with the admin role from its user selector. Its task query includes direct task assignment and team membership but omits tasks reachable through `Project.assigned_user`. The selected board is fetched once when the filter changes and is not refreshed afterward. These differences mean the various boards do not agree about assignment visibility and an administrator cannot see their own assigned work.

### Daily Work

`projects.views` currently defines `delete_task` twice. The later Kanban permission view replaces the daily-task deletion view at import time, so the daily endpoint resolves to the wrong behavior. Daily tasks also accept arbitrary titles and have no link to an assigned Kanban task.

### Notifications

The notification API only retrieves explicit many-to-many recipients and ignores active notifications addressed to all users or to a role. Mark-as-read does not store state. The unread count uses `is_pinned` as a proxy for unread state. The admin overview does not apply recipient filtering, its date tabs do not filter, and the notification widget is not mounted consistently.

### Imports and Publications

A project CSV example exists, but there is no production-quality project import command behind it. Papers have a limited Excel upload path; books and conferences do not have equivalent validated import paths. Publication models are separate from projects and therefore do not automatically participate in assignments or Kanban workflows.

## Architecture

### Shared Work Scope

Add a single service module responsible for answering:

- which projects a user can view;
- which projects are assigned to a user;
- which tasks a user can work on;
- whether a user can change a specific task; and
- which users an administrator or centre head may inspect.

All staff, manager, and administrator views use this service. Direct project assignment, direct task assignment, project creation/ownership where applicable, and `Assignment`/`TeamMember` membership are handled explicitly. Querysets use `select_related`, `prefetch_related`, and `distinct` to avoid duplicate rows and excessive queries.

Authorization is enforced in views and services, not only by hiding controls in templates.

### Administrator Boards

The admin navigation gains **My Projects**. It displays only work assigned to the logged-in administrator. The administrator can change task status and comments but cannot silently change project ownership through the Kanban interface.

The existing staff viewer remains read-only. Its user filter includes every inspectable active user, including administrators when permitted. Selecting a user loads their board from the shared scope. The board exposes an explicit refresh action and polls every 30 seconds while visible. Responses contain a last-updated value so the interface can communicate freshness.

Selecting a card opens a compact Bootstrap modal. The modal uses a table to display project name, description, type, status, research centre, project manager, team members, responsibility, task title, task type, task status, priority, progress, comments, created date, task due date, and project due date. Due dates are classified as overdue, due today, due within seven days, or normal. Missing values display `Not set`; a missing project displays `Project unavailable` without raising an exception.

The server returns an error status for failed board requests. JavaScript checks `response.ok`, replaces loading indicators with a visible error state, and never inserts a login page or error document as if it were a valid board.

### Staff Daily Work

`DailyTask` retains its legacy `title`, `is_done`, and `created_at` fields. It gains:

- nullable `task` foreign key to `Task` using `SET_NULL`;
- `work_date`, indexed and defaulted to the local date; and
- nullable `completed_at`.

The task relationship is nullable solely for legacy compatibility and deletion safety. Existing rows remain readable. New rows created through the staff interface must select a task from the shared assigned-task pool; free-text creation is rejected server-side.

The daily page shows the selected day's work and lets the user move between dates. The selection list omits tasks already added for that user and date. A uniqueness constraint on user, linked task, and work date prevents duplicate selections while allowing multiple legacy rows with a null task.

Completing a linked daily item atomically marks the daily item complete, stores `completed_at`, and moves its Kanban task to `done`, allowing the model's existing progress mapping to set progress to 100. Reopening a daily item restores the Kanban task to `in_progress`; it does not guess the task's earlier status. Legacy unlinked items can still be completed or removed safely.

Daily and Kanban endpoints receive distinct function and URL names to eliminate the current Python name collision.

### Publication Projects

`Book`, `Paper`, and `Conference` each gain a nullable, unique link to `Project`. The link uses `SET_NULL`, so deleting or temporarily missing a project cannot make publication pages fail. `Project.PROJECT_TYPES` gains `conference`.

A publication-project service creates or updates both records inside `transaction.atomic()`. Publication forms and importers call this service rather than duplicating synchronization logic. Project name, description, status, due date, research centre, and assignment are derived from validated publication input. Publication-specific fields remain on the publication model.

A data migration backfills existing publications. It creates a project when no link exists and records deterministic names when duplicate titles exist. If a row lacks enough data for an assignment, the project is created unassigned and the publication page displays a setup warning. Backfill failures are reported and do not make normal page rendering depend on a successful link.

### Bulk Import Contract

Provide UTF-8 CSV templates and acceptable-values documentation for:

- users;
- ordinary projects;
- books;
- papers; and
- conferences.

Project and publication rows use a required, stable `import_key` for idempotent reruns. User references use usernames, with separate columns for project manager, lead author, co-authors, reviewers, and team members. Multi-user fields use a documented semicolon delimiter. Templates include research centre, status, dates, descriptions, and type-specific metadata. Passwords appear only in the user template and are never included in project/publication templates.

Management commands perform two phases:

1. Parse and validate the complete batch without writing.
2. Write validated records using atomic row transactions and produce created, updated, skipped, and failed counts.

`--dry-run` is mandatory in the documented workflow before a live import. Unknown usernames, invalid choices, duplicate keys, impossible dates, and cross-centre assignments produce row-numbered errors. A failed row cannot leave an orphaned publication or project. Rerunning a successful file updates the matching import key without creating duplicates.

Import execution is restricted to management commands for the first release. This avoids accepting large untrusted files through the web interface and keeps production rollout auditable.

### Notifications

Add per-user receipt state rather than modifying a global notification when one user reads it. A receipt links a notification and user, records `read_at`, and has a unique constraint for that pair.

One notification service applies active-time and audience rules consistently for all pages and APIs. It supports `all`, `role`, and `specific` audiences. Mark-as-read verifies that the notification is visible to the requesting user before creating or updating the receipt.

The admin overview and notification widget use the same service. Unread counts come from receipts, pinned state remains independent, and Today/Week/Month controls perform real filtering. The widget is included in the appropriate base templates. Rendering escapes notification text rather than constructing unsafe HTML from untrusted values.

### Concurrency and Capacity

The expected 23-user load does not justify Redis or Celery. Normal database writes use PostgreSQL transactions and targeted indexes. Status updates change only the intended columns. Board refreshes occur every 30 seconds only while a board is visible.

Email delivery is not allowed to roll back project, assignment, publication, or import data. Email calls remain behind the existing email service so a background queue can be introduced later without changing domain behavior.

## Error Handling and Compatibility

- New relationships are nullable during rollout.
- Templates use fallbacks for missing projects, users, research centres, and dates.
- Detail endpoints return 404 for missing records and 403 for unauthorized records.
- JSON and partial endpoints return structured error responses.
- Import validation finishes before live writes begin.
- Database changes use forward migrations and do not delete existing data.
- Existing unlinked daily records and publications continue to render.
- The implementation does not alter the existing uncommitted proxy/CSRF settings change.

## Verification Strategy

Follow test-driven development for each behavior. Tests must fail for the intended missing behavior before production code is changed.

Create a dedicated file-backed SQLite database named `test.db` under a test-artifact directory excluded from version control. Test settings must never resolve to the production database. Recreate the database from migrations for the integration run.

Coverage includes:

- identical assignment visibility across staff, manager, admin My Projects, staff viewer, and daily pool;
- an admin assigned directly and through a team membership;
- staff-filter refresh after another client changes a task;
- modal details and all due-date alert states;
- authorization failures for cross-user changes;
- daily selection, duplicate prevention, completion synchronization, reopening, and legacy null links;
- publication creation, update, backfill, and missing-link rendering;
- dry-run, idempotent rerun, invalid-row rollback, usernames, multi-user fields, and every CSV type;
- notification audience, active windows, per-user read state, unread count, and date filters;
- page rendering for empty databases and partially linked legacy data; and
- the full existing Django test suite.

Before production deployment, run migrations and imports against `test.db`, execute the full suite, perform a browser smoke test for each role, and archive the import summary. Production deployment and production imports are separate, explicitly approved actions.

## Out of Scope

- Redis, Celery, or another background queue.
- Real-time WebSockets; 30-second refresh is sufficient for the stated load.
- Replacing the existing role model.
- Production deployment or production data import as part of implementation.
- Broad visual redesign beyond the requested navigation, board, table, modal, alerts, and error states.
