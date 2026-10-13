import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.core.management.base import CommandError


@dataclass(frozen=True)
class ImportIssue:
    row_number: int
    field: str
    message: str


@dataclass
class ImportSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0


def read_csv_rows(path_value, required_headers):
    path = Path(path_value)
    if not path.is_file():
        raise CommandError(f'CSV file not found: {path}')
    with path.open('r', newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = sorted(set(required_headers) - headers)
        if missing:
            raise CommandError(f'Missing required CSV headers: {", ".join(missing)}')
        return [
            (row_number, {key: (value or '').strip() for key, value in row.items()})
            for row_number, row in enumerate(reader, start=2)
        ]


def split_usernames(value):
    return [item.strip() for item in (value or '').split(';') if item.strip()]


def parse_date_value(value, *, row_number, field, required=False):
    if not value:
        if required:
            raise CommandError(f'Row {row_number}: {field} is required.')
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError as exc:
        raise CommandError(f'Row {row_number}: {field} must use YYYY-MM-DD.') from exc
