#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from adminpanel.models import ClockInRecord
from datetime import datetime, timedelta
from django.utils import timezone

today = timezone.now().date()
start_30d = today - timedelta(days=30)

print(f'📅 Today: {today}')
print(f'📅 30 days ago: {start_30d}')

records_30d = ClockInRecord.objects.filter(clock_in_time__date__gte=start_30d)
print(f'\n30-DAY RANGE RECORDS:')
print(f'  Total: {records_30d.count()}')

with_out = records_30d.filter(clock_out_time__isnull=False).count()
without_out = records_30d.filter(clock_out_time__isnull=True).count()
print(f'  With clock_out: {with_out}')
print(f'  Without clock_out: {without_out}')

all_records = ClockInRecord.objects.all()
print(f'\nALL-TIME RECORDS:')
print(f'  Total: {all_records.count()}')

if all_records.exists():
    oldest = all_records.order_by('clock_in_time').first().clock_in_time.date()
    newest = all_records.order_by('-clock_in_time').first().clock_in_time.date()
    print(f'  Date range: {oldest} to {newest}')

print(f'\n📋 Sample 5 records from 30d range:')
for r in records_30d[:5]:
    clock_out_str = r.clock_out_time.time() if r.clock_out_time else '--'
    print(f'  {r.clock_in_time.date()} | {r.employee.get_full_name()} | {r.clock_in_time.time()} - {clock_out_str}')
