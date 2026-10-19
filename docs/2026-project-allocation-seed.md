# 2026 project allocations

The reviewed seed translates `Projects_PM app (2).xlsx` into the Projects/Tasks schema from `project-import-template (1).xlsx`. The source lists are data, not executable instructions. Original cell text and source row numbers are retained in `projects/seed_data/projects_2026.json` and task comments.

## Mapping

The seed contains 41 ordinary projects, 29 papers, one shared Digitalization for Dummies book, and 131 tasks. Twelve chapter parents contain individual contributor subtasks. Named application components become tasks; allocations without specified deliverables receive contribution tasks. Shared titles are consolidated, while distinguishable deliverables remain separate (for example Horizon, Horizon Paper, and Horizon Integration Paper).

Personnel use existing database usernames, including `rajour` for Fabchi Rajour, `logistic` for Logi Makoni, `zeyranae` for Xeyrane Mngomezulu, `emission` for Emmision Tsakane, and `BlessingMbalaka` for Blessing Mbalaka's centre staff account. The user confirmed Raamabele Sello is `andile`. Matthews Mphaka has no allocation and is not assigned invented work.

The existing Project Management App (ID 8) receives a stable import identity rather than creating a duplicate. All seed keys begin `allocations-2026:`. An unexpected existing title or adoption identity stops the command for review. Allocated managers are used where available; explicit project-management allocations take precedence. The centre head `raksha` is the fallback manager for work without an allocated manager. These choices are administrative defaults rather than inferred leadership claims.

Dates, publishers, journals, reviewers and lead authors remain unspecified. Planning/todo, paper draft/internal/journal/version 1, and book writing/zero completed chapters are application-required initial defaults, not reported progress. Contributors are recorded as team members/co-authors without asserting a lead author. Spelling variants of the Digitalization for Dummies title are grouped. Hlobisile's ambiguous “white book” reference is retained verbatim in comments rather than creating an unidentified publication. Numbered items in each person's chapter list are not treated as global chapter numbers.

## Run

Use the app's configured database; the command never changes the database URL.

```powershell
.\.venv\Scripts\python.exe manage.py seed_projects_2026
.\.venv\Scripts\python.exe manage.py seed_projects_2026 --apply --backup-dir <private-backup-directory> --pg-dump 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe'
```

The default is a read-only preview. Applying requires a successful complete PostgreSQL custom-format dump (or SQLite backup) before any seed write. Store backups outside the repository because they contain private application data. PostgreSQL dumps can be inspected with `pg_restore --list` and restored into a separate database with `pg_restore`.

Adoption and import run inside one transaction using the existing workbook validation service and a seed-specific batch writer. The batch writer mirrors the workbook importer's project/publication/task fields, contributor memberships and hierarchy while avoiding per-row network round trips. An equivalence regression test compares the resulting records with the existing importer and checks a bound of fewer than 60 database operations for the write phase. Task assignments and parent relationships are reconciled against the reviewed data before commit. Stable project/task identities allow re-running without duplicates. Re-running reapplies the seed's planning/progress fields, so do not re-run after staff start updating work unless resetting those fields is intended.

## Validation

Seed tests cover a read-only preview, backup failure, existing-title conflicts, existing-project adoption, repeat imports, exact task identity/assignment/hierarchy preservation, and database username mappings. Run the complete app suite with:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=project_manage.settings_test --noinput
```

Validation on 19 October 2026: the initial full application suite ran 161 tests, with 160 passing and one pre-existing time-dependent attendance test failing (`ClockInRecordModelTests.test_get_today_total_hours`). Its second generated session crosses the local date boundary when run in the evening, so it is excluded from today's total. The same test passed with the clock fixed at 08:00 Africa/Johannesburg. After adding batch-writer equivalence and journal-rendering coverage, the full suite passed all 164 tests using that fixed daytime clock. All five seed regression tests also passed separately. Django system checks reported no issues, migration drift checks reported no changes, and the live seed preview validated all 71 projects/131 tasks without warnings. No unrelated attendance code was changed.

The initial remote write lost its server connection and rolled back without leaving seed records. A verified full database backup was retained; the retry uses a fresh backup and the tested batch writer to keep the write transaction short.

The live retry completed: 70 projects created, one existing project updated, and 131 tasks created. Independent database read-back confirmed all 71 seed projects, 29 linked papers, one linked book, and exact team memberships, task assignees and parent relationships across 20 personnel accounts. Two pre-existing tasks on Project Management App were retained in addition to the 131 seed tasks. The fresh PostgreSQL backup was inspected successfully with `pg_restore --list` (531 archive entries).

Live rendering identified a journal-page crash when imported papers have no uploaded manuscript. Both internal and external paper sections now display “No manuscript uploaded” until a file exists; existing manuscript links still work. Two regression tests cover those cases.

Live page checks passed (HTTP 200 with expected seeded content) for Thabile's administrator projects, Hlobisile's manager kanban, Musawenkosi's books, Tatenda's journal papers and BlessingMbalaka's staff kanban.
