#!/usr/bin/env python
"""
Script to create test employee data and clock-in records for testing the User Activity Analytics dashboard.
Run with: python manage.py shell < create_test_activity_data.py
Or: python create_test_activity_data.py
"""

import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from django.utils import timezone
from users.models import CustomUser
from adminpanel.models import ClockInRecord
from projects.models import Task, Assignment

def create_test_employees():
    """Create test employee accounts"""
    test_employees = [
        {
            'username': 'john_doe',
            'email': 'john.doe@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'role': 'employee',
        },
        {
            'username': 'jane_smith',
            'email': 'jane.smith@example.com',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'role': 'employee',
        },
        {
            'username': 'mike_johnson',
            'email': 'mike.johnson@example.com',
            'first_name': 'Mike',
            'last_name': 'Johnson',
            'role': 'employee',
        },
        {
            'username': 'sarah_williams',
            'email': 'sarah.williams@example.com',
            'first_name': 'Sarah',
            'last_name': 'Williams',
            'role': 'employee',
        },
        {
            'username': 'david_brown',
            'email': 'david.brown@example.com',
            'first_name': 'David',
            'last_name': 'Brown',
            'role': 'employee',
        },
    ]
    
    employees = []
    for emp_data in test_employees:
        user, created = CustomUser.objects.get_or_create(
            username=emp_data['username'],
            defaults={
                'email': emp_data['email'],
                'first_name': emp_data['first_name'],
                'last_name': emp_data['last_name'],
                'role': emp_data['role'],
                'is_active': True,
            }
        )
        if created:
            user.set_password('testpass123')
            user.save()
            print(f"✅ Created employee: {user.get_full_name()}")
        else:
            print(f"⏭️  Employee already exists: {user.get_full_name()}")
        employees.append(user)
    
    return employees

def create_clock_in_records(employees):
    """Create realistic clock-in records for test employees"""
    
    # Define work patterns (start time, end time, days per week)
    work_patterns = [
        {'start': 8, 'end': 17, 'days': 5},      # 9 hours/day, 5 days/week (John)
        {'start': 9, 'end': 18, 'days': 4},      # 9 hours/day, 4 days/week (Jane)
        {'start': 8, 'end': 16, 'days': 5},      # 8 hours/day, 5 days/week (Mike)
        {'start': 10, 'end': 19, 'days': 5},     # 9 hours/day, 5 days/week (Sarah)
        {'start': 7, 'end': 15, 'days': 5},      # 8 hours/day, 5 days/week (David)
    ]
    
    records_created = 0
    today = datetime.now().date()
    
    for emp_idx, employee in enumerate(employees):
        pattern = work_patterns[emp_idx]
        
        # Create 80 days of clock records
        for day_offset in range(0, 90):
            current_date = today - timedelta(days=day_offset)
            
            # Skip weekends (0-4 = Mon-Fri, 5-6 = Sat-Sun)
            if current_date.weekday() >= 5:
                continue
            
            # Randomly skip some days (sick days, days off) - 10% chance
            import random
            if random.random() < 0.1:
                continue
            
            # Create clock-in record with timezone-aware datetime
            naive_clock_in = datetime.combine(
                current_date,
                datetime.min.time().replace(
                    hour=pattern['start'],
                    minute=random.randint(0, 30)  # Random arrival time (within 30 mins)
                )
            )
            clock_in_time = timezone.make_aware(naive_clock_in)
            
            # Add break (30 min to 1 hour)
            break_duration = random.randint(30, 60)
            
            # Calculate clock-out time (work hours + break)
            work_hours = pattern['end'] - pattern['start']
            naive_clock_out = datetime.combine(
                current_date,
                datetime.min.time().replace(
                    hour=pattern['end'],
                    minute=random.randint(0, 30)
                )
            )
            
            # Add small variance to end time (±15 minutes)
            variance = timedelta(minutes=random.randint(-15, 15))
            naive_clock_out = naive_clock_out + variance
            
            # Make timezone-aware
            clock_out_time = timezone.make_aware(naive_clock_out)
            
            # Create the record
            try:
                record, created = ClockInRecord.objects.get_or_create(
                    employee=employee,
                    clock_in_time=clock_in_time,
                    defaults={
                        'clock_out_time': clock_out_time,
                        'status': 'completed',
                    }
                )
                if created:
                    records_created += 1
            except Exception as e:
                print(f"⚠️  Error creating record for {employee.get_full_name()} on {current_date}: {str(e)}")
    
    print(f"\n✅ Created {records_created} clock-in records")

def create_test_tasks(employees):
    """Create test tasks and assignments"""
    from projects.models import Project
    
    # Create or get a test project
    project, created = Project.objects.get_or_create(
        name="Test Project",
        defaults={
            'description': "Test project for activity tracking",
            'status': 'active',
        }
    )
    
    task_names = [
        "Dashboard Development",
        "API Integration",
        "Database Optimization",
        "UI Design",
        "Testing & QA",
    ]
    
    for idx, task_name in enumerate(task_names):
        task, created = Task.objects.get_or_create(
            title=task_name,
            defaults={
                'project': project,
                'description': f"Test task for {task_name}",
                'status': 'in_progress',
                'priority': 'high',
            }
        )
        
        if created:
            print(f"✅ Created task: {task_name}")
        
        # Assign to random employee
        import random
        assigned_to = random.choice(employees)
        
        # Create assignment if not exists
        assignment, created = Assignment.objects.get_or_create(
            task=task,
            assigned_to=assigned_to,
            defaults={
                'status': 'in_progress',
                'progress_percentage': random.randint(20, 95),
            }
        )
        
        if created:
            print(f"✅ Assigned {task_name} to {assigned_to.get_full_name()}")

def main():
    print("=" * 60)
    print("📊 Creating Test Employee Data")
    print("=" * 60)
    
    print("\n1️⃣  Creating test employees...")
    employees = create_test_employees()
    
    print("\n2️⃣  Creating clock-in records...")
    create_clock_in_records(employees)
    
    print("\n3️⃣  Creating test tasks and assignments...")
    create_test_tasks(employees)
    
    print("\n" + "=" * 60)
    print("✨ Test data creation complete!")
    print("=" * 60)
    print("\n📈 Test Data Summary:")
    print(f"  • Total employees: {len(employees)}")
    print(f"  • Total clock records: {ClockInRecord.objects.count()}")
    print(f"  • Total tasks: {Task.objects.count()}")
    print(f"  • Total assignments: {Assignment.objects.count()}")
    print("\n🔗 Access the dashboard at: http://127.0.0.1:8000/adminpanel/manage-users/")
    print("   (Scroll down to see the User Activity Analytics section)\n")

if __name__ == '__main__':
    main()
