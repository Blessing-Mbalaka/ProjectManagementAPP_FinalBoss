# Project Workbook Import Design

## Purpose

Give project managers a safe, repeatable way to create or update projects, publication metadata, portfolios, team membership, tasks, subtasks, and task assignments from one Excel workbook. The same workbook and validation rules must work through the Project Manager Assignment page and a Django management command so it can be used for interactive bulk uploads and controlled seed data.

## Success Criteria

- The Project Manager Assignment page provides **Download Template** and **Upload Workbook** actions.
- A workbook contains `Instructions`, `Projects`, and `Tasks` sheets.
- Projects support the existing `software`, `book`, `paper`, and `conference` project types.
- `portfolio` is optional free text stored on the project for later filtering.
- Publication-specific author and metadata fields are validated only when required by the selected project type.
- Rows in `Tasks` explicitly identify parent tasks; repeated project names never imply a parent-child relationship.
- Workbook uploads support team membership, task assignment, and nested subtasks.
- Validation produces sheet, row, field, and reason for every rejected item before the user confirms a write.
- The management command supports `--dry-run` and uses the same parser, validator, and writer as the web flow.
- Re-importing a valid workbook updates matching records without creating duplicate projects or tasks.

## Scope

### Included

- Nullable free-text `portfolio` on `Project`.
- A nullable import identity on tasks, or an equivalent project-scoped identity that provides idempotent task updates.
- Excel template generation and download.
- Manager-only workbook upload, preview, confirmation, and result reporting.
- A shared import service and a management command for seed operations.
- Project, publication, team, task, subtask, and assignee creation or updates.
- Validation, transaction boundaries, permissions, and automated tests.

### Excluded

- Deleting projects, tasks, or team members because they are absent from a later workbook.
- Arbitrarily deep organizational portfolio models or controlled portfolio vocabularies.
- Background queues for imports.
- Importing user accounts; referenced usernames must already exist.
- Importing manuscript or conference-paper binary files through the workbook.

## Workbook Format

The downloadable `.xlsx` file contains three sheets. Column headings are fixed and comparisons of choice values are case-insensitive after trimming whitespace. Blank optional cells are permitted. Multi-user fields use semicolon-separated usernames.

### `Instructions`

This sheet explains:

- allowed project, publication, task status, priority, and task-type values;
- date formatting as `YYYY-MM-DD`;
- semicolon-separated username fields;
- how parent tasks are referenced;
- conditional fields for each project type;
- that users and research centres must already exist;
- how re-import matching works; and
- a compact example suitable for a person or AI to follow.

### `Projects`

One row represents one project. The sheet contains these columns:

| Column | Requirement | Meaning |
| --- | --- | --- |
| `import_key` | Required | Stable unique identity used for safe re-imports. |
| `project_name` | Required | Display name; unique within the workbook. |
| `portfolio` | Optional | Free-text portfolio label used for later filtering. |
| `description` | Optional | Project description. |
| `project_type` | Required | `software`, `book`, `paper`, or `conference`. |
| `project_status` | Required | One of the existing `Project.STATUS_CHOICES` values. |
| `due_date` | Optional | Project due date. |
| `project_manager_username` | Required | Existing manager username. |
| `research_centre` | Required | Existing research-centre name. |
| `team_usernames` | Optional | Semicolon-separated existing usernames. |
| `publication_status` | Conditional | Required for `book`, `paper`, and `conference`; validated against that model's status choices. |
| `lead_author` | Conditional | Free-text author fallback. Required when a publication has no valid `lead_author_username`. |
| `lead_author_username` | Optional | Existing user used as the linked lead author where the current model supports it. |
| `co_author_usernames` | Optional | Semicolon-separated existing users for papers and conferences. |
| `reviewer_usernames` | Optional | Semicolon-separated existing users for papers and conferences. |
| `publisher` | Optional | Book publisher. |
| `total_chapters` | Optional | Positive integer for books; defaults to `1`. |
| `completed_chapters` | Optional | Non-negative integer not greater than `total_chapters`; defaults to `0`. |
| `internal_external` | Conditional | Required for papers and conferences: `internal` or `external`. |
| `paper_type` | Conditional | Required for papers: `journal` or `conference`. |
| `version` | Conditional | Required for papers. |
| `abstract` | Optional | Paper or conference abstract. |
| `target_journal` | Optional | Paper target journal. |
| `conference_name` | Conditional | Required for conferences. |
| `conference_date` | Optional | Conference date. |
| `location` | Optional | Conference location. |
| `submission_date` | Optional | Publication submission date. |
| `decision_date` | Optional | Publication decision date. |

For `software`, all publication columns are ignored when blank and rejected when populated with contradictory publication data. For publications, the importer creates or updates the linked `Book`, `Paper`, or `Conference` through the existing publication-project synchronization service. It never changes a linked publication to a different kind in place; that conflict is a validation error.

The project manager, team members, linked authors, co-authors, reviewers, and task assignees must belong to the project's research centre when they have a centre assigned. A referenced task assignee or linked publication contributor is automatically added to project membership if not already present. Automatically created assignments receive a descriptive default responsibility such as `Task assignee` or `Publication contributor`; an existing responsibility is not overwritten.

### `Tasks`

One row represents one task or subtask. The sheet contains these columns:

| Column | Requirement | Meaning |
| --- | --- | --- |
| `project_name` | Required | Exact name of one project in the `Projects` sheet. |
| `task_name` | Required | Task title, unique within the project. |
| `parent_task` | Optional | Exact `task_name` of another task in the same project. Blank means a top-level task. |
| `assigned_to` | Optional | Existing username. |
| `responsibility` | Optional | Responsibility used when the assignee is added to the project team. |
| `status` | Optional | Existing task status; defaults to `todo`. |
| `priority` | Optional | `Low`, `Medium`, or `High`. |
| `task_type` | Optional | Existing `Task.PROJECT_PHASES` value. |
| `due_date` | Optional | Task due date. |
| `comments` | Optional | Initial or updated task comments. |

Parent resolution is independent of row order. A parent may be another row in the workbook or an existing task in the matched project. The validator rejects missing parents, self-parenting, cycles, duplicate task names within a project, references to projects absent from the `Projects` sheet, and parent references that cross project boundaries.

Tasks are matched by project identity and normalized task name. A re-import updates the matched task. New task rows create tasks. The import never deletes tasks omitted from the workbook. Parent changes are allowed after the full proposed hierarchy passes cycle validation.

## Architecture

### Shared Import Service

A focused service module owns the complete workflow:

1. Read the workbook and verify required sheet and column names.
2. Normalize cells without losing meaningful free text.
3. Validate every project and task row without writing.
4. Build an immutable preview describing creates, updates, warnings, and errors.
5. Apply an approved preview using the same normalized data.

The service exposes separate parse/validate and apply operations. Views and management commands call these operations rather than maintaining separate import rules. The apply operation does not trust client-posted preview contents; confirmation references a server-stored, short-lived normalized import payload or re-parses the uploaded file using a tamper-resistant token.

The parser must cap file size and row counts, reject macros and unsupported formats, and never evaluate formulas. Only `.xlsx` is accepted for this workflow.

### Data Model

`Project` gains a nullable, blank `portfolio` character field with an index suitable for later exact filtering. Existing records migrate with `NULL` and remain valid.

Task identity must support deterministic re-import without globally constraining ordinary task titles. The preferred design is a nullable `import_key` scoped uniquely to a project. For workbook rows, the importer derives a stable task key from the normalized task name when an explicit key is not exposed in the user-facing template. Manual tasks retain a null import key. Before adding the constraint, the migration must tolerate all existing manual tasks.

No new portfolio table is introduced. Existing `Assignment`, `TeamMember`, `Task.parent_task`, and publication relations remain authoritative.

### Web Flow

The Project Manager Assignment page gains:

- **Download Template**, returning a generated workbook with examples and allowed values;
- **Upload Workbook**, opening a file-selection modal; and
- an import preview page or modal.

Upload is limited to authenticated project managers and other roles already authorized to manage the affected projects. Managers may only create or update projects in their own research centre. Existing project updates also require current project-management scope.

The preview groups results into projects, publications, memberships, tasks, and subtasks. It shows create/update counts and all errors with sheet and Excel row number. Confirmation is disabled while validation errors exist. The initial release uses all-or-nothing workbook validation: no row is written until every error is corrected. This avoids ambiguous dependencies where a valid subtask depends on a rejected parent or project.

After confirmation, the page shows final created and updated counts and links to affected projects. Normal Django messages provide a compact success or failure summary on return to the assignment page.

### Seed Command

Add a management command with this interface:

```text
python manage.py import_project_workbook <path> --dry-run
python manage.py import_project_workbook <path>
```

`--dry-run` prints the same validation preview and performs no writes. A live run refuses to proceed if any validation error exists and prints created and updated totals on success. The command is idempotent and suitable for system seed data after referenced users and research centres exist.

## Validation and Error Handling

Errors use this format:

```text
Tasks row 5, parent_task: "Build front-end" was not found in project "Website Redesign"; task "Create homepage" was not added.
```

Validation covers:

- workbook extension, size, required sheets, headers, and row limits;
- required and conditionally required fields;
- duplicate `import_key` and project names in the workbook;
- conflicting existing project or publication identities;
- all model choice values and numeric/date ranges;
- unknown usernames or research centres;
- role and research-centre eligibility;
- project-management authorization for updates;
- publication author and type requirements;
- duplicate task names, missing parents, cross-project parents, and cycles; and
- due dates that are malformed or logically inconsistent where a constraint is explicit.

The full workbook is validated before writes. Application uses a database transaction per workbook so an unexpected database failure rolls back projects, publications, memberships, and task hierarchies together. Email or notification delivery occurs after commit and cannot roll back imported data. Delivery failures are shown as warnings.

## Idempotency and Matching

- Projects match by `import_key`; names are validated for clarity but are not the database identity.
- Publication records match through the project's existing one-to-one publication relationship.
- Tasks match by project-scoped import identity derived from normalized task names.
- Team assignments use the existing unique project/member pair.
- Re-import updates supplied mutable fields and leaves unspecified unrelated records intact.
- The importer never silently changes a project's type or linked publication kind.

## Testing Strategy

Follow test-driven development. Tests cover:

- template download, sheet names, headers, examples, and allowed-value guidance;
- nullable portfolio migration, persistence, display, and import;
- successful software, book, paper, and conference imports;
- conditional publication fields and author behavior;
- existing username and research-centre enforcement;
- automatic team membership for authors and task assignees;
- parent resolution before and after the child row;
- existing manual task used as a parent;
- missing parents, cycles, self-parenting, duplicate tasks, and cross-project parents;
- preview behavior and confirmation authorization;
- manager centre and project-scope permissions;
- all-or-nothing validation and rollback after an application failure;
- dry-run behavior and zero writes;
- idempotent re-imports with updates and no duplicates;
- malformed, oversized, and unsupported workbooks;
- safe handling of formulas and uploaded filenames;
- command and web paths producing equivalent results; and
- regression coverage for manual project, assignment, and task creation on the existing page.

Verification runs targeted import tests, project and manager test suites, migrations against the isolated test database, the full Django suite, and a browser smoke test of template download, upload preview, confirmation, and the resulting task hierarchy.

## Rollout and Compatibility

- Migrations are additive and preserve all existing projects and tasks.
- Existing CSV project and publication commands remain available; the workbook command is the recommended combined workflow.
- Existing manual creation and assignment forms remain functional.
- No production data is imported automatically during deployment.
- Production seed execution requires a successful `--dry-run` followed by an explicit live command.
