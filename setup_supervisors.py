import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from users.models import CustomUser
from projects.models import StudentProfile

print("\n" + "="*70)
print("ADDING DUMMY SUPERVISORS FOR TESTING")
print("="*70 + "\n")

# Create supervisor users if they don't exist
supervisors_data = [
    {
        'username': 'prof_smith',
        'first_name': 'Prof.',
        'last_name': 'Smith',
        'email': 'smith@university.edu'
    },
    {
        'username': 'prof_telukdarie',
        'first_name': 'Prof.',
        'last_name': 'Telukdarie',
        'email': 'telukdarie@university.edu'
    },
    {
        'username': 'prof_johnson',
        'first_name': 'Prof.',
        'last_name': 'Johnson',
        'email': 'johnson@university.edu'
    },
]

created_supervisors = []

for sup_data in supervisors_data:
    supervisor, created = CustomUser.objects.get_or_create(
        username=sup_data['username'],
        defaults={
            'first_name': sup_data['first_name'],
            'last_name': sup_data['last_name'],
            'email': sup_data['email'],
            'role': 'admin',  # Supervisors are admins
            'is_staff': True,
            'is_active': True
        }
    )
    if created:
        print(f"✓ Created supervisor: {supervisor.get_full_name()} ({supervisor.username})")
        created_supervisors.append(supervisor)
    else:
        print(f"• Supervisor already exists: {supervisor.get_full_name()} ({supervisor.username})")
        created_supervisors.append(supervisor)

print(f"\n{len(created_supervisors)} supervisors available for assignment\n")

# Get all students that don't have a supervisor assigned
students_without_supervisor = StudentProfile.objects.filter(supervisor__isnull=True)

print(f"Found {students_without_supervisor.count()} students without supervisors\n")

if students_without_supervisor.exists() and created_supervisors:
    print("Assigning supervisors to students:\n")
    for i, student_profile in enumerate(students_without_supervisor):
        # Assign supervisors in round-robin fashion
        supervisor = created_supervisors[i % len(created_supervisors)]
        student_profile.supervisor = supervisor
        student_profile.save()
        print(f"✓ {student_profile.user.get_full_name()} → assigned to {supervisor.get_full_name()}")

print("\n" + "="*70)
print("SUPERVISOR ASSIGNMENT COMPLETE")
print("="*70)

# Print summary
print("\nCurrent Student-Supervisor Assignments:\n")
all_students = StudentProfile.objects.all()
for student in all_students:
    supervisor_name = student.supervisor.get_full_name() if student.supervisor else "UNASSIGNED"
    print(f"  {student.user.get_full_name()} → {supervisor_name}")

print("\n" + "="*70 + "\n")
