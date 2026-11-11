# Project Management Application

README author and project maintainer: **Blessing Mbalaka (st10466840)**

Documentation updated: **11 November 2026**

A Django application for research and operational project delivery: create a project, assign its lead and team, plan tasks and subtasks, track progress, and review delivery and financial information through role-specific pages. The application also manages book, paper and conference workflows, notifications, security review and IT operations.

This repository is restricted software. Obtain written authorisation before copying, cloning, modifying, deploying or redistributing it. See [LICENSE](LICENSE) for the scope, exceptions and contributor rights.

## Start here

| You need to | Read |
| --- | --- |
| Install or run the application | [Local setup](#local-setup) |
| Configure secrets and email | [.env.example](.env.example) |
| Operate the application or train users | [System handover and user manual](handover/System%20handover%20and%20user%20manual.html) |
| Deploy payroll protection, backups or restore | [IT operations deployment notes](handover/IT%20operations%20deployment%20notes.txt) |
| Move the database and salary keys to another host | The salary-key custody and transfer section in the handover |
| Activate weekly account emails | [Weekly check-in instructions](#weekly-account-check-ins) and [deployment notes](handover/Weekly%20login%20check-in%20deployment%20notes.txt) |
| Prepare a bulk project import | [Import workbook guide](outputs/import_templates/README.md) |

## Application workflows

- Project creation, lead assignment and team allocation feed shared task, subtask, Kanban and progress views.
- Staff assigned to a project can add tasks and subtasks through the same task-creation workflow used by project managers. This does not grant staff project-creation rights.
- Books, papers and conferences have their own research delivery workflows.
- Financial administration includes cost centres, expenditure, forecasts and editable financial project tracking for authorised roles. Admin can assign bid work to an active Financial Admin in the same centre; newly assigned follow-up work starts in To Do at 0%, with Admin able to view all assignees or filter one. Financial Admin uses its own engagement-notes layout, My Projects and personal Kanban.
- Individual salary records are encrypted in the database and masked in finance views; salary totals remain available to the application.
- Notifications, account-security confirmation, role-change alerts and page-activity records support account oversight.
- IT operations separates its overview, backup schedules/history and database recovery into distinct pages. Recovery archives are emailed to selected users rather than retained as the only copy on the application server.

### Roles

The primary roles are listed below. Permissions are enforced by the server as well as navigation visibility; an exposed link or a changed browser value does not grant access. Assignment, centre scope and any explicitly granted group entitlements still apply.

| Role | Main workflow |
| --- | --- |
| Admin | User administration, project allocation, delivery oversight, finance and IT operations. |
| Dean | Leadership and research oversight through the available dashboards. |
| Centre Head | Centre-scoped project management, team oversight and authorised financial workflows. |
| Overseer | Centre Head-style nonfinancial oversight; financial pages, actions and navigation are excluded. |
| Project Manager | Manage assigned projects, allocate work and maintain tasks, subtasks and delivery progress. The stored role value is `manager`. |
| Financial Admin | Financial administration and assigned financial project delivery. |
| Staff | Work on assigned projects; create project tasks/subtasks and contribute progress and research work. |
| Supervisor / Student | Their assigned research and collaboration workflows. |
| IT | Backup schedules, emailed recovery archives, controlled restore, security alerts and page-activity monitoring. This role alone does not grant finance or user-administration access. |

Only the actual Admin and Financial Admin primary roles can manage protected salary records. A generic superuser flag alone does not grant salary-management permission. Use the handover for the full role and button workflows.

## Local setup

Use Python 3.12. Django, PostgreSQL connectivity, encryption and storage dependencies are listed in [requirements.txt](requirements.txt). SQLite is supported for local development; production uses PostgreSQL. Docker configuration is not supplied in this checkout.

The commands below assume an authorised checkout and PowerShell, opened in the repository root.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Create a local configuration only if one does not already exist.
if (!(Test-Path project_manage/.env)) {
    Copy-Item .env.example project_manage/.env
}
```

Edit `project_manage/.env` before running migrations:

1. Keep `DEBUG=True` for local work.
2. Set a private `SECRET_KEY`.
3. Set `SALARY_ENCRYPTION_KEYS` to a unique Fernet key for a new installation, or preserve the existing key list when moving an existing database.
4. Leave `DATABASE_URL` empty for local SQLite, or set a dedicated local PostgreSQL URL. Confirm that it does not point to production before running local migration or maintenance commands.
5. Configure SMTP if email delivery is needed. Backups and automatic weekly emails are disabled by default.

For a **new installation**, generate the two independent secrets:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Put the first value in `SECRET_KEY` and the second in `SALARY_ENCRYPTION_KEYS`. Do not commit the populated environment file or paste secrets into logs, issues or the handover. Do not replace an existing salary key simply because the host is changing.

Then initialise and run:

```powershell
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/users/login/`. Create your own administrator credentials; these instructions do not provide a default password. On Linux/macOS, use `.venv/bin/python` in place of the Windows interpreter path.

## Environment configuration

[.env.example](.env.example) is the configuration reference. It contains placeholders and comments, not working credentials. Django reads local values from `project_manage/.env`; host-supplied environment values take precedence. Render services use their own Environment settings, not edits to this example file.

| Setting | Purpose |
| --- | --- |
| `SECRET_KEY` | Django application secret. Set a private value, especially with `DEBUG=False`. |
| `DATABASE_URL` | Database connection string; absent/empty uses local SQLite. |
| `SALARY_ENCRYPTION_KEYS` | Required payroll key list. First key encrypts; later keys read older records and backups. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP connection and authentication. |
| `DEFAULT_FROM_EMAIL`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | Sender and transport settings. Do not enable both TLS and SSL. |
| `DB_BACKUP_ENABLED` | Allows database backups; does not start a worker. |
| `DB_BACKUP_KEEP_LOCAL` | Defaults to `False`: remove the database payload after accepted email delivery. |
| `DB_BACKUP_DIR` | Private temporary staging directory, outside media and static directories. |
| `DB_BACKUP_MAX_EMAIL_BYTES` | Attachment limit; defaults to 15 MiB. |
| `DB_RESTORE_ENABLED`, `DB_MAINTENANCE_MODE` | Explicit gates for controlled recovery. The operator must also stop normal traffic. |
| `LOGIN_PINGS_ENABLED` | Enables Monday scheduling inside a running operations worker. It does not start a scheduler in the web app. |
| `AZURE_CONNECTION_STRING`, `AZURE_CONTAINER` | Optional Azure/Azurite upload storage. Without a connection string, uploads use local media. |

### Salary keys and migration

Salary values use authenticated encryption, not password-style hashing. The application decrypts them in memory to calculate totals. The encryption key is kept outside the database; someone holding both the database and its key can decrypt the values.

Preserve the **exact existing key list** when migrating a database. Transfer it through an approved secret manager or restricted encrypted channel and configure it on the destination web service and workers before migrations or recovery. Keep a protected recovery copy separate from database archives and backup mailboxes. Losing all matching keys makes the salary records unreadable.

Migration `0037` checks the payroll key before changing finance tables; `0038` encrypts existing salary rows and redacts salary audit values. The encryption backfill is intentionally irreversible through normal migration rollback. Preserve a recovery backup and drain old writers before deployment. Read the [IT deployment notes](handover/IT%20operations%20deployment%20notes.txt) before applying these migrations to an existing system.

## IT operations

Sign in as IT or Admin and use these pages:

| Page | Route |
| --- | --- |
| Overview | `/adminpanel/it/` |
| Backups & Schedules | `/adminpanel/it/backups/` |
| Restore Database | `/adminpanel/it/recovery/` |

Choose active users with valid addresses as backup recipients, save the schedule and test a manual backup. A recovery ZIP contains the database snapshot and verification manifest. The database payload is removed from the app server after accepted email delivery by default; metadata remains. Backups cover the database, not uploaded media or Blob objects.

Run the operations worker separately from the web service:

```text
python manage.py run_backup_jobs --loop
```

Alternatively, a host scheduler can invoke `python manage.py run_backup_jobs` periodically. Saving an in-app schedule does not create a host worker. PostgreSQL backups and restore require compatible `pg_dump` and `pg_restore` tools in the runtime.

Missing SMTP configuration or failed backup email delivery produces an IT warning in the operations pages and notification bell. SMTP acceptance is not proof of inbox delivery; verify the received attachment and rehearse recovery in staging.

Recovery requires maintenance gates, a verified imported archive, the current operator password and the typed snapshot confirmation. A new safety archive must be emailed successfully before replacement. Successful restore invalidates sessions and disables backup schedules. Follow the [restore instructions](handover/IT%20operations%20deployment%20notes.txt); do not treat the maintenance flag as a substitute for draining requests or stopping other workers.

## Weekly account check-ins

Each active account with a valid email address receives a private email using its actual last-login date. Today's logins receive neutral wording; never-used accounts are told that they have not logged in yet. Messages contain no app link. A database reservation prevents repeat sends for the same account and calendar week.

Preview without sending:

```text
python manage.py send_login_pings
```

Send explicitly:

```text
python manage.py send_login_pings --send
```

Choose one automatic scheduling method:

| Method | Activation |
| --- | --- |
| Running operations worker | Set `LOGIN_PINGS_ENABLED=True` on the worker running `python manage.py run_backup_jobs --loop`. It handles Mondays from 09:00 Africa/Johannesburg, even if database backups are disabled. |
| Hosting cron job | Leave the flag `False`; schedule `python manage.py send_login_pings --send` with UTC cron `0 7 * * 1`. |

Setting the flag on a Render **web service** alone does not run scheduled work. Editing `.env.example` does not activate Render either. The explicit send command works independently of the flag. A cron job or running worker must share the production database and SMTP configuration.

After a failed or uncertain send, inspect provider logs before reconciling the delivery record. The job retries database bookkeeping after a disconnect, not the SMTP send. See the [weekly email deployment notes](handover/Weekly%20login%20check-in%20deployment%20notes.txt).

## Optional Azure or Azurite media

Set a complete `AZURE_CONNECTION_STRING` and the existing `AZURE_CONTAINER` name. For Azurite, use endpoints reachable by the application and by browsers that follow file links. Verify upload and download from the deployed environment.

Without a connection string, uploads use local media. Existing files are not migrated automatically. Preserve media separately from database backups; signed storage links expire and may require a page refresh.

## Project workbook import

Use the workbook supplied through the application or [project-import-template.xlsx](outputs/import_templates/project-import-template.xlsx). Research centres and referenced users must exist first.

```text
python manage.py import_project_workbook outputs/import_templates/project-import-template.xlsx --dry-run
python manage.py import_project_workbook outputs/import_templates/project-import-template.xlsx
```

Review the preview before writing. Existing `import_key` values update matching projects. Unknown author usernames are reported and skipped; missing managers, team members, reviewers or assignees stop the affected import validation. External author names belong in `external_authors`.

## Validation

Use the dedicated test settings so tests do not target the production database:

```text
python manage.py check --settings=project_manage.settings_test
python manage.py makemigrations --check --dry-run --settings=project_manage.settings_test
python manage.py test --settings=project_manage.settings_test --noinput
```

The latest recorded suite passed **316 tests**. Test settings use isolated SQLite databases under `test_artifacts`; that directory and local credentials are excluded from source control. Read the [recorded test results](handover/Automated%20test%20results.txt) and handover for browser checks and their limits. PostgreSQL staging recovery and real backup-mailbox delivery must be verified before enabling production backup/restore operations.

## Render deployment

[render.yaml](render.yaml) defines the web service. Its build command installs requirements, collects static assets and runs migrations; Gunicorn serves the application.

Before deployment, configure `DEBUG=False`, a private `SECRET_KEY`, the intended `DATABASE_URL`, the preserved salary key list, SMTP and any optional storage settings. Configure payroll keys **before** the migration build. Back up the current database/media and drain writes for a payroll backfill.

Workers and cron jobs are separate processes/services; the web start command does not activate them. Give them the required database and secrets independently. Follow the [handover](handover/System%20handover%20and%20user%20manual.html) for migration, recovery and post-deployment checks.

## Repository layout

| Path | Contents |
| --- | --- |
| `project_manage/` | Django settings, routing and test runner. |
| `users/` | Accounts, role enforcement, role auditing and weekly login emails. |
| `projects/` | Shared project, team and task workflows. |
| `manager/` | Project-manager views and delivery controls. |
| `adminpanel/` | Administration, research/finance workflows, security and IT operations. |
| `templates/` | Server-rendered pages and shared layouts. |
| `static/` | Source CSS, JavaScript and images. |
| `staticfiles/` | Collected deployment assets; edit source assets under `static/`. |
| `outputs/import_templates/` | Workbook templates and import guidance. |
| `handover/` | User manual, operations notes and recorded verification results. |

## Contributors

README author and maintainer: **Blessing Mbalaka**, also recorded in Git as `st10466840`.

Contributor credits from repository history:

- Blessing Mbalaka (`st10466840`, `Blessing-Mbalaka`)
- HopeLotriet
- Mpho Nkadimeng (`gnkadimeng`)
- Tiisetsopudinyane

Git aliases sharing the same contributor email have been consolidated. These credits identify recorded contributors; they do not transfer anyone's copyright or assert ownership of third-party libraries.

## Licence and access

The original application and documentation are subject to the restricted-use notice in [LICENSE](LICENSE). No general permission is granted to clone, download, copy, modify, deploy, redistribute, sublicense or sell them without prior written authorisation from the relevant rights holders, subject to the exceptions in that notice. Third-party components keep their own licences and notices. Existing valid permissions are not revoked by this notice.

A licence is not a technical copy-protection mechanism. GitHub's public-repository terms permit viewing and forking through the service; a repository must be private if access itself needs restriction. See [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository). This README does not grant access or permission to contribute; request authorisation from the maintainer through the project's agreed communication channel.
