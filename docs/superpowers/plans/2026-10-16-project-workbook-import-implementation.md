# Project Workbook Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manager-facing Excel workbook workflow and matching seed command that safely create or update projects, portfolios, publications, authors, teams, tasks, subtasks, and assignments.

**Architecture:** A focused `projects.workbook_import` package owns workbook generation, parsing, validation, signed previews, and atomic application. The web views and management command are thin adapters over that shared service; existing publication synchronization and project-scope rules remain authoritative.

**Tech Stack:** Python 3, Django 5.2, SQLite/PostgreSQL, `openpyxl`, Bootstrap 5, Django signing, Django `TestCase`.

**Spec:** `docs/superpowers/specs/2026-10-16-project-workbook-import-design.md`

## Global Constraints

- Accept only `.xlsx`; cap uploads at 2 MiB, `Projects` at 250 data rows, and `Tasks` at 2,000 data rows.
- Workbook sheets are exactly `Instructions`, `Projects`, and `Tasks`; dates use `YYYY-MM-DD`; multi-value cells use semicolons.
- Project types remain exactly `software`, `book`, `paper`, and `conference`.
- `portfolio` is nullable free text; no portfolio lookup table is introduced.
- Internal authors are related by user ID; explicit external names are stored separately; unknown/cross-centre author usernames are skipped with warnings.
- Manager, explicit team-member, reviewer, and task-assignee identity/centre failures are blocking errors.
- Validation is all-or-nothing and precedes writes; application runs in one database transaction.
- Re-import updates matching records and never deletes omitted projects, tasks, memberships, or publications.
- Emails/notifications run after commit and cannot roll back imported data.
- Preserve the user's existing staged changes in `staticfiles/js/dashboard.js` and `staticfiles/js/finance.js`; never include them in feature commits.

## Review Focus

- Formula cells or macro-enabled/renamed files must be rejected rather than evaluated or accepted as plain values (Task 2 tests).
- Case/whitespace variants of project and task names must not create ambiguous matches (Task 3 tests).
- An expired, modified, or differently authenticated preview token must never apply changes (Task 5 tests).
- A database error after publication creation must roll back every project, membership, and task write (Task 4 tests).
- Blank `external_authors` on re-import intentionally clears the list and must be visible in the preview (Tasks 3 and 4 tests).

---

### Task 1: Add Import-Safe Data Relationships

**Files:**
- Modify: `projects/models.py`
- Create: `projects/migrations/0012_project_portfolio_task_import_key.py`
- Modify: `manager/models.py`
- Create: `manager/migrations/0011_publication_author_relations.py`
- Test: `projects/test_workbook_models.py`

**Interfaces:**
- Produces: `Project.portfolio: str | None`; `Task.import_key: str | None`; conditional uniqueness of `(project, import_key)`; `Book.lead_author_user`; `Book.co_authors_users`; `Book.external_authors`; `Paper.external_authors`; `Conference.external_authors`.
- Consumes: existing `Project`, `Task`, `Book`, `Paper`, `Conference`, and `settings.AUTH_USER_MODEL`.

- [ ] **Step 1: Write failing model tests**

Add tests named `test_project_portfolio_is_nullable_and_indexed`, `test_task_import_key_is_unique_only_within_project`, `test_manual_tasks_can_keep_null_import_keys`, `test_book_supports_linked_lead_and_multiple_coauthors`, and `test_publications_default_external_authors_to_empty_list`. Assert duplicate non-null task keys in one project raise `IntegrityError`, while the same key in another project and multiple null keys succeed.

- [ ] **Step 2: Run the model tests and verify the missing fields fail**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_models --settings=project_manage.settings_test -v 2`

Expected: FAIL because the new fields and relations do not exist.

- [ ] **Step 3: Add the model fields and constraints**

Use `Project.portfolio = models.CharField(max_length=255, null=True, blank=True, db_index=True)`, `Task.import_key = models.CharField(max_length=64, null=True, blank=True)`, and a conditional `UniqueConstraint(fields=['project', 'import_key'], condition=Q(import_key__isnull=False), name='unique_task_import_key_per_project')`. Add nullable/many-to-many book user relations with distinct related names and `external_authors = models.JSONField(default=list, blank=True)` to all three publication models.

- [ ] **Step 4: Generate and inspect additive migrations**

Run: `.\.venv\Scripts\python.exe manage.py makemigrations projects manager --settings=project_manage.settings_test`

Expected: only the named additive fields and conditional constraint; no destructive operations or unrelated model changes.

- [ ] **Step 5: Run model and migration checks**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_models --settings=project_manage.settings_test -v 2`

Expected: PASS.

Run: `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=project_manage.settings_test`

Expected: `No changes detected`.

- [ ] **Step 6: Commit only Task 1 files**

```powershell
git commit --only -m "feat: add workbook import data relationships" -- projects/models.py projects/migrations/0012_project_portfolio_task_import_key.py manager/models.py manager/migrations/0011_publication_author_relations.py projects/test_workbook_models.py
```

### Task 2: Define and Generate the Workbook Contract

**Files:**
- Modify: `requirements.txt`
- Create: `projects/workbook_import/__init__.py`
- Create: `projects/workbook_import/schema.py`
- Create: `projects/workbook_import/workbook.py`
- Test: `projects/test_workbook_format.py`

**Interfaces:**
- Produces: `PROJECT_COLUMNS: tuple[str, ...]`, `TASK_COLUMNS: tuple[str, ...]`, `WorkbookReadResult`, `build_template_workbook() -> bytes`, and `read_workbook(upload, *, max_bytes=2097152) -> WorkbookReadResult`.
- Consumes: Task 1 model choices and `openpyxl==3.1.5` with formula evaluation disabled.

- [ ] **Step 1: Write failing template contract tests**

Test `build_template_workbook()` by loading its bytes with `openpyxl.load_workbook(..., data_only=False, read_only=True)`. Assert exact sheet order, exact `Projects` and `Tasks` headers from the spec, allowed values and semicolon/date guidance on `Instructions`, and sample parent/subtask rows using `Website Redesign`.

- [ ] **Step 2: Write failing workbook safety tests**

Add tests for a missing sheet, unknown/missing header, `.xlsm`/non-`.xlsx` filename, bytes over 2 MiB, project/task row caps, and any cell whose data type is `f`. Each must return a structured workbook-level error without evaluating the formula.

- [ ] **Step 3: Run format tests and verify imports/functions are missing**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_format --settings=project_manage.settings_test -v 2`

Expected: FAIL because `projects.workbook_import` does not exist.

- [ ] **Step 4: Add the pinned dependency and schema constants**

Add `openpyxl==3.1.5` to `requirements.txt`. In `schema.py`, define the exact headers, limits, sheet names, choice-value helpers, and frozen `WorkbookCellError`/`WorkbookReadResult` dataclasses.

- [ ] **Step 5: Implement workbook generation and safe reading**

Implement `build_template_workbook() -> bytes` and `read_workbook(upload, *, max_bytes=2097152) -> WorkbookReadResult` in `workbook.py`. Use `openpyxl` without VBA, never calculate formulas, normalize blank trailing rows, retain Excel row numbers, and return errors instead of raising for user-correctable format problems.

- [ ] **Step 6: Run format tests**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_format --settings=project_manage.settings_test -v 2`

Expected: PASS.

- [ ] **Step 7: Commit only Task 2 files**

```powershell
git commit --only -m "feat: define project workbook format" -- requirements.txt projects/workbook_import/__init__.py projects/workbook_import/schema.py projects/workbook_import/workbook.py projects/test_workbook_format.py
```

### Task 3: Validate and Preview Projects, Publications, Authors, and Task Trees

**Files:**
- Create: `projects/workbook_import/validation.py`
- Test: `projects/test_workbook_validation.py`

**Interfaces:**
- Consumes: `WorkbookReadResult` from Task 2, Task 1 fields, existing user/centre/project scope, model choices.
- Produces: frozen serializable `ProjectRow`, `TaskRow`, `ImportIssue`, `ImportAction`, and `WorkbookImportPreview`; `validate_workbook(read_result, *, actor) -> WorkbookImportPreview`; `normalize_name(value: str) -> str`; `task_import_key(title: str) -> str`.

- [ ] **Step 1: Write failing successful-preview tests**

Cover a software project with nullable portfolio, out-of-order parent/subtask rows, task assignments, and automatic team membership actions. Cover book, paper, and conference rows with type-specific fields, one lead author, multiple co-authors, reviewers, and normalized external authors.

- [ ] **Step 2: Write failing matching and author-warning tests**

Assert projects match by `import_key`; task names match case/whitespace-insensitively within a project; duplicate normalized project/task names are blocking; existing manual tasks may be parents; unknown/cross-centre author usernames become warnings and are omitted; unknown managers, explicit team users, reviewers, and assignees are blocking. Assert a blank external-author cell previews a clear from-nonempty-to-empty update.

- [ ] **Step 3: Write failing graph and conditional-field tests**

Assert errors include sheet, Excel row, field, and reason for missing parent, self-parent, cycle, cross-project parent, invalid choices/dates/counts, completed chapters above total chapters, contradictory software publication data, missing conference name, and an attempted publication-kind change.

- [ ] **Step 4: Run validation tests and verify failure**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_validation --settings=project_manage.settings_test -v 2`

Expected: FAIL because the validator and preview types do not exist.

- [ ] **Step 5: Implement normalized immutable preview construction**

Implement the produced interfaces. Use Unicode trim/casefold for comparisons, keep original display strings, derive task import keys as `task:` plus the first 32 hex characters of SHA-256 over the normalized title, resolve the complete parent graph before returning, and calculate create/update actions without writing.

- [ ] **Step 6: Run validation tests**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_validation --settings=project_manage.settings_test -v 2`

Expected: PASS with `Project`, `Task`, and publication row counts unchanged by every preview test.

- [ ] **Step 7: Commit only Task 3 files**

```powershell
git commit --only -m "feat: validate project workbook previews" -- projects/workbook_import/validation.py projects/test_workbook_validation.py
```

### Task 4: Apply Validated Workbooks and Expose the Seed Command

**Files:**
- Create: `projects/workbook_import/application.py`
- Modify: `manager/publication_projects.py`
- Create: `projects/management/commands/import_project_workbook.py`
- Test: `projects/test_workbook_application.py`
- Test: `projects/test_workbook_command.py`

**Interfaces:**
- Consumes: `WorkbookImportPreview` from Task 3; existing `sync_publication_project` and assignment models.
- Produces: `ImportResult`; `apply_workbook_preview(preview, *, actor) -> ImportResult`; command `import_project_workbook <path> [--dry-run]`.

- [ ] **Step 1: Write failing atomic application tests**

Assert one valid preview creates/updates all four project types, portfolio, linked publications, internal/external authors, memberships, tasks, assignments, and parent links. Assert a second application updates without duplicates or deletions. Patch the task-save phase to raise and assert the database contains none of the attempted project, publication, membership, or task writes.

- [ ] **Step 2: Write failing compatibility tests for publication synchronization**

Assert workbook application retains the explicit `project_status`, `description`, `due_date`, `portfolio`, manager, and research centre after publication synchronization, while ordinary existing calls to `sync_publication_project(publication, actor=...)` preserve current behavior.

- [ ] **Step 3: Write failing command tests**

Assert `--dry-run` reports create/update/warning/error counts and writes nothing; live mode refuses any preview with errors; a valid run is idempotent; warnings for skipped author usernames do not block writes; and the command output identifies the affected workbook rows.

- [ ] **Step 4: Run application and command tests and verify failure**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_application projects.test_workbook_command --settings=project_manage.settings_test -v 2`

Expected: FAIL because the application service and command do not exist.

- [ ] **Step 5: Implement one-transaction application**

Implement `apply_workbook_preview(preview, *, actor) -> ImportResult` under `transaction.atomic`. Re-authorize all existing project updates for `actor`; upsert projects by `import_key`, publications through an extended backward-compatible synchronization interface, team assignments by project/member, then tasks in parent-safe order. Use `transaction.on_commit` for notifications and return delivery failures as warnings.

- [ ] **Step 6: Implement the shared command adapter**

Implement `import_project_workbook` using Task 2 reading, Task 3 validation, and Task 4 application. `--dry-run` never calls the application service. Format every issue with sheet, row, field, and message; raise `CommandError` on blocking validation errors.

- [ ] **Step 7: Run application, command, and legacy import tests**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_application projects.test_workbook_command projects.test_project_imports manager.test_publication_imports --settings=project_manage.settings_test -v 2`

Expected: PASS.

- [ ] **Step 8: Commit only Task 4 files**

```powershell
git commit --only -m "feat: apply and seed project workbooks" -- projects/workbook_import/application.py manager/publication_projects.py projects/management/commands/import_project_workbook.py projects/test_workbook_application.py projects/test_workbook_command.py
```

### Task 5: Add Secure Preview and Confirmation to the Manager UI

**Files:**
- Create: `projects/workbook_import/tokens.py`
- Modify: `manager/views.py`
- Modify: `manager/urls.py`
- Modify: `templates/manager/assign.html`
- Create: `templates/manager/project_workbook_preview.html`
- Test: `manager/test_project_workbook_ui.py`

**Interfaces:**
- Consumes: Tasks 2–4 template, preview, and application services.
- Produces: `sign_preview(preview, *, actor_id) -> str`; `unsign_preview(token, *, actor_id, max_age=1800) -> WorkbookImportPreview`; URL names `download_project_workbook`, `preview_project_workbook`, and `apply_project_workbook`.

- [ ] **Step 1: Write failing access and download tests**

Assert unauthenticated users redirect to login; `staff` and `student` receive 403; `manager`, `centrehead`, `dean`, and `admin` may download; response content type is the XLSX MIME type and the filename is `project-import-template.xlsx`.

- [ ] **Step 2: Write failing preview-rendering tests**

Post a valid workbook and assert create/update sections, nested task labels, external-author changes, warnings, and an enabled confirmation form appear. Post an invalid workbook and assert exact sheet/row/field errors appear and no confirmation control is rendered.

- [ ] **Step 3: Write failing token and confirmation tests**

Assert modified, expired, and different-user tokens return 400/403 without writes. Assert application re-checks current project scope so a manager who loses access after preview receives 403. Assert a valid token applies once, redirects to `assign_projects`, and a replay cannot create duplicates.

- [ ] **Step 4: Run UI tests and verify failure**

Run: `.\.venv\Scripts\python.exe manage.py test manager.test_project_workbook_ui --settings=project_manage.settings_test -v 2`

Expected: FAIL because the routes, views, template, and token functions do not exist.

- [ ] **Step 5: Implement signed previews and role guard**

Use Django signing with salt `projects.workbook-import.v1`, compression, embedded actor ID, and `max_age=1800`. Add a focused role predicate allowing active `manager`, `centrehead`, `dean`, and `admin` users; all update authorization is still enforced per project during validation and application.

- [ ] **Step 6: Implement thin download, preview, and apply views**

Keep views in `manager/views.py` as adapters: validate file presence/name/size, call shared services, render the preview, verify the signed token, call application, and use Django messages. Return 400 for malformed/expired tokens and 403 for identity/scope failures.

- [ ] **Step 7: Add the Assignment-page controls and preview template**

Place **Download Template** and **Upload Workbook** beside **New Project**. Use a Bootstrap multipart modal accepting `.xlsx`. Render summary cards, issue tables, proposed projects/publications/team changes, task/subtask hierarchy, and the confirmation form with escaped Django template output.

- [ ] **Step 8: Run UI and existing manager workflow tests**

Run: `.\.venv\Scripts\python.exe manage.py test manager.test_project_workbook_ui manager.tests.ManagerProjectCreationTests projects.tests.TaskModelTests --settings=project_manage.settings_test -v 2`

Expected: PASS.

- [ ] **Step 9: Commit only Task 5 files**

```powershell
git commit --only -m "feat: add manager project workbook upload" -- projects/workbook_import/tokens.py manager/views.py manager/urls.py templates/manager/assign.html templates/manager/project_workbook_preview.html manager/test_project_workbook_ui.py
```

### Task 6: Verify the Complete Workflow and Document Seeding

**Files:**
- Create: `outputs/import_templates/project-import-template.xlsx`
- Modify: `outputs/import_templates/README.md`
- Modify: `readme.md`
- Test: `projects/test_project_workbook_e2e.py`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: checked-in example workbook generated by `build_template_workbook()` and operator instructions for UI upload, `--dry-run`, live import, allowed values, author behavior, and re-import matching.

- [ ] **Step 1: Write the failing end-to-end test**

Generate a workbook containing one software project and one publication project, multiple authors, an external author, team members, a parent task, and subtasks. Run the shared preview/application flow and assert the manager assignment page, Kanban scope, and linked publication expose the imported records without duplicate queries or missing relations.

- [ ] **Step 2: Run the end-to-end test and fix only integration defects**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_project_workbook_e2e --settings=project_manage.settings_test -v 2`

Expected: PASS after resolving any cross-task interface defects.

- [ ] **Step 3: Generate the checked-in workbook from production code**

Run a short Django shell invocation that calls `build_template_workbook()` and writes only `outputs/import_templates/project-import-template.xlsx`. Confirm opening it through `openpyxl` yields the three expected sheets and no formulas.

- [ ] **Step 4: Document both supported workflows**

Update the import-template README and root README with UI steps and these commands:

```powershell
.\.venv\Scripts\python.exe manage.py import_project_workbook outputs\import_templates\project-import-template.xlsx --dry-run
.\.venv\Scripts\python.exe manage.py import_project_workbook outputs\import_templates\project-import-template.xlsx
```

State that users and research centres must exist first, unknown author usernames are warnings, external authors require the explicit column, and production live import is a separate operator action.

- [ ] **Step 5: Run targeted and full verification**

Run: `.\.venv\Scripts\python.exe manage.py test projects.test_workbook_models projects.test_workbook_format projects.test_workbook_validation projects.test_workbook_application projects.test_workbook_command projects.test_project_workbook_e2e manager.test_project_workbook_ui --settings=project_manage.settings_test -v 2`

Expected: PASS.

Run: `.\.venv\Scripts\python.exe manage.py test --settings=project_manage.settings_test -v 1`

Expected: full suite PASS with no access to the production database.

Run: `.\.venv\Scripts\python.exe manage.py check --deploy --settings=project_manage.settings_test`

Expected: no new errors introduced by this feature; record any pre-existing deployment warnings separately.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 6: Browser smoke test**

As a project manager, download the template, populate a project/task hierarchy, upload it, inspect the preview, confirm it, and verify the resulting project, portfolio, publication authors, team, and nested tasks on the Assignment page. Verify an invalid parent produces a visible error and no writes.

- [ ] **Step 7: Commit only Task 6 files**

```powershell
git commit --only -m "docs: add project workbook seed template" -- outputs/import_templates/project-import-template.xlsx outputs/import_templates/README.md readme.md projects/test_project_workbook_e2e.py
```
