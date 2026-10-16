# Bulk Import Templates

All files are UTF-8 CSVs. Remove the example row and keep the header unchanged. User references are exact, existing usernames; multi-user fields use semicolons with no commas.

Always validate first:

```powershell
.\.venv\Scripts\python.exe manage.py seed_users_from_csv outputs\import_templates\users.csv --research-centre "Research Centre Name" --dry-run
.\.venv\Scripts\python.exe manage.py import_projects outputs\import_templates\projects.csv --dry-run
.\.venv\Scripts\python.exe manage.py import_publications outputs\import_templates\books.csv --dry-run
.\.venv\Scripts\python.exe manage.py import_publications outputs\import_templates\papers.csv --dry-run
.\.venv\Scripts\python.exe manage.py import_publications outputs\import_templates\conferences.csv --dry-run
```

Run the same command without `--dry-run` only after validation succeeds. `import_key` is the stable external identity: rerunning a row with the same key updates it instead of creating a duplicate.

Users must be imported before projects and publications. The user importer requires one `--research-centre` value per batch. Do not store real production passwords in these template files.

## Combined Project Workbook

`project-import-template.xlsx` is the recommended format for new project-manager imports. It contains:

- `Instructions` — allowed values and formatting guidance;
- `Projects` — projects, nullable free-text portfolios, publication metadata, teams, and authors; and
- `Tasks` — tasks, explicit parent tasks, assignees, priorities, and due dates.

Users and research centres must already exist. Internal authors use exact usernames and remain linked if their display names change. Unknown or cross-centre author usernames are skipped with warnings. Put people without system accounts in the explicit semicolon-separated `external_authors` column. Other unknown usernames, including managers, reviewers, team members, and task assignees, are blocking errors.

Always validate the workbook first:

```powershell
.\.venv\Scripts\python.exe manage.py import_project_workbook outputs\import_templates\project-import-template.xlsx --dry-run
.\.venv\Scripts\python.exe manage.py import_project_workbook outputs\import_templates\project-import-template.xlsx
```

The live command is a separate operator action. `import_key` identifies a project across re-imports; normalized task names identify tasks within that project. Re-importing updates matched records and does not delete omitted records.

Project managers can perform the same workflow from **Project Manager Assignment** using **Download Template** and **Upload Workbook**. The web flow shows a validation preview and requires confirmation before saving.
