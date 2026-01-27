import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from users.models import CustomUser
from projects.models import StudentProfile

print("\n" + "="*80)
print("CREATING TEST SUPERVISOR AND STUDENT USERS")
print("="*80 + "\n")

# Create test supervisors with supervisor role
supervisors_data = [
    {
        'username': 'prof_muranga',
        'password': 'TestPass123!',
        'first_name': 'Dr.',
        'last_name': 'Muranga',
        'email': 'muranga@university.edu',
        'role': 'supervisor'
    },
    {
        'username': 'prof_adeyemi',
        'password': 'TestPass123!',
        'first_name': 'Prof.',
        'last_name': 'Adeyemi',
        'email': 'adeyemi@university.edu',
        'role': 'supervisor'
    },
    {
        'username': 'prof_okonkwo',
        'password': 'TestPass123!',
        'first_name': 'Dr.',
        'last_name': 'Okonkwo',
        'email': 'okonkwo@university.edu',
        'role': 'supervisor'
    },
]

print("CREATING SUPERVISOR ACCOUNTS (role='supervisor'):\n")
created_supervisors = []

for sup_data in supervisors_data:
    supervisor, created = CustomUser.objects.get_or_create(
        username=sup_data['username'],
        defaults={
            'first_name': sup_data['first_name'],
            'last_name': sup_data['last_name'],
            'email': sup_data['email'],
            'role': sup_data['role'],
            'is_staff': False,  # Supervisors are NOT staff
            'is_active': True
        }
    )
    if created:
        supervisor.set_password(sup_data['password'])
        supervisor.save()
        print(f"✓ Created: {supervisor.get_full_name():25} | Username: {supervisor.username:15} | Password: {sup_data['password']}")
        created_supervisors.append(supervisor)
    else:
        print(f"• Exists:  {supervisor.get_full_name():25} | Username: {supervisor.username:15}")
        created_supervisors.append(supervisor)

print(f"\n{len(created_supervisors)} supervisors ready\n")

# Create test students and assign to supervisors
students_data = [
    {
        'username': 'student_test1',
        'password': 'StudentPass123!',
        'first_name': 'Alice',
        'last_name': 'Johnson',
        'email': 'alice.johnson@student.edu',
        'program': 'Masters in Engineering',
        'research_title': 'AI Applications in Healthcare',
        'year': '2nd Year'
    },
    {
        'username': 'student_test2',
        'password': 'StudentPass123!',
        'first_name': 'Bob',
        'last_name': 'Smith',
        'email': 'bob.smith@student.edu',
        'program': 'PhD in Computer Science',
        'research_title': 'Machine Learning for Climate Prediction',
        'year': '3rd Year'
    },
    {
        'username': 'student_test3',
        'password': 'StudentPass123!',
        'first_name': 'Carol',
        'last_name': 'Williams',
        'email': 'carol.williams@student.edu',
        'program': 'Masters in Data Science',
        'research_title': 'Big Data Analytics in Finance',
        'year': '1st Year'
    },
]

print("CREATING STUDENT ACCOUNTS (role='student'):\n")

for i, student_data in enumerate(students_data):
    student_user, created = CustomUser.objects.get_or_create(
        username=student_data['username'],
        defaults={
            'first_name': student_data['first_name'],
            'last_name': student_data['last_name'],
            'email': student_data['email'],
            'role': 'student',
            'is_staff': False,
            'is_active': True
        }
    )
    
    if created:
        student_user.set_password(student_data['password'])
        student_user.save()
        print(f"✓ Created: {student_user.get_full_name():20} | Username: {student_user.username:15} | Password: {student_data['password']}")
    else:
        print(f"• Exists:  {student_user.get_full_name():20} | Username: {student_user.username:15}")
    
    # Create or update StudentProfile
    supervisor = created_supervisors[i % len(created_supervisors)]
    student_profile, profile_created = StudentProfile.objects.get_or_create(
        user=student_user,
        defaults={
            'supervisor': supervisor,
            'program': student_data['program'],
            'research_title': student_data['research_title'],
            'year': student_data['year'],
            'co_supervisor': ''
        }
    )
    
    if not profile_created:
        student_profile.supervisor = supervisor
        student_profile.program = student_data['program']
        student_profile.research_title = student_data['research_title']
        student_profile.year = student_data['year']
        student_profile.save()
    
    print(f"  └─ Assigned to: {supervisor.get_full_name()}\n")

print("="*80)
print("TEST USER SETUP COMPLETE!")
print("="*80 + "\n")

# Print summary
print("LOGIN CREDENTIALS:\n")
print("SUPERVISORS (role='supervisor'):")
for sup_data in supervisors_data:
    print(f"  • Username: {sup_data['username']:25} | Password: {sup_data['password']}")

print("\nSTUDENTS (role='student'):")
for student_data in students_data:
    print(f"  • Username: {student_data['username']:25} | Password: {student_data['password']}")

print("\n" + "="*80)
print("STUDENT-SUPERVISOR ASSIGNMENTS:\n")

all_students = StudentProfile.objects.all().select_related('user', 'supervisor')
for student_profile in all_students:
    supervisor_name = student_profile.supervisor.get_full_name() if student_profile.supervisor else "UNASSIGNED"
    print(f"  {student_profile.user.get_full_name():20} → {supervisor_name}")

print("\n" + "="*80 + "\n")
