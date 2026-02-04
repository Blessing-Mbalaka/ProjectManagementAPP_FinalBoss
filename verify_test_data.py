#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from users.models import CustomUser
from adminpanel.models import ClockInRecord

employees = CustomUser.objects.filter(role='employee')
records = ClockInRecord.objects.all()

print("\n" + "="*60)
print("✅ TEST DATA VERIFICATION")
print("="*60)
print(f"\n👥 Total Test Employees: {employees.count()}")
for emp in employees:
    emp_records = records.filter(employee=emp).count()
    print(f"   • {emp.get_full_name()}: {emp_records} clock records")

print(f"\n📊 Total Clock Records: {records.count()}")

if records.exists():
    recent = records.latest('clock_in_time')
    oldest = records.earliest('clock_in_time')
    print(f"   • Date Range: {oldest.clock_in_time.date()} to {recent.clock_in_time.date()}")
    
print("\n" + "="*60)
print("🎉 Test data is ready!")
print("="*60)
print("\n🚀 Next Steps:")
print("   1. Start the server: python manage.py runserver")
print("   2. Navigate to: http://127.0.0.1:8000/adminpanel/manage-users/")
print("   3. Scroll down to 'User Activity Analytics' section")
print("   4. Try filtering by employee and date range")
print("\n")
