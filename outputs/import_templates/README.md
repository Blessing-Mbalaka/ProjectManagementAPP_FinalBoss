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
