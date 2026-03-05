from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

CustomUser = get_user_model()


class Command(BaseCommand):
    help = 'Inject fake users with passwords for testing purposes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='TestPass123',
            help='Password for all injected users (default: TestPass123)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Delete existing test users and recreate them'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password']
        force = options['force']

        # Define test users for each role
        test_users = [
            {
                'username': 'test_admin',
                'email': 'admin@testproject.com',
                'first_name': 'Admin',
                'last_name': 'Test',
                'role': 'admin',
            },
            {
                'username': 'test_supervisor',
                'email': 'supervisor@testproject.com',
                'first_name': 'Supervisor',
                'last_name': 'Test',
                'role': 'supervisor',
            },
            {
                'username': 'test_manager',
                'email': 'manager@testproject.com',
                'first_name': 'Manager',
                'last_name': 'Test',
                'role': 'manager',
            },
            {
                'username': 'test_financialadmin',
                'email': 'financialadmin@testproject.com',
                'first_name': 'Financial',
                'last_name': 'Admin',
                'role': 'financialadmin',
            },
            {
                'username': 'test_staff',
                'email': 'staff@testproject.com',
                'first_name': 'Staff',
                'last_name': 'Test',
                'role': 'staff',
            },
            {
                'username': 'test_student',
                'email': 'student@testproject.com',
                'first_name': 'Student',
                'last_name': 'Test',
                'role': 'student',
            },
        ]

        created_users = []
        skipped_users = []

        for user_data in test_users:
            username = user_data['username']
            
            # Check if user already exists
            user_exists = CustomUser.objects.filter(username=username).exists()
            
            if user_exists:
                if force:
                    # Delete existing user
                    CustomUser.objects.filter(username=username).delete()
                    self.stdout.write(
                        self.style.WARNING(f"Deleted existing user: {username}")
                    )
                else:
                    skipped_users.append(username)
                    self.stdout.write(
                        self.style.WARNING(f"User already exists (skipped): {username}")
                    )
                    continue

            try:
                # Create user with password hashing via CustomUserManager
                user = CustomUser.objects.create_user(
                    username=username,
                    email=user_data['email'],
                    password=password,
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    role=user_data['role'],
                )
                created_users.append({
                    'username': username,
                    'email': user_data['email'],
                    'role': user_data['role'],
                    'password': password,
                })
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created user: {username} (role: {user_data['role']})")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error creating user {username}: {str(e)}")
                )

        # Display summary
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("FAKE USERS INJECTION SUMMARY"))
        self.stdout.write("="*70)
        
        if created_users:
            self.stdout.write(f"\n✓ Successfully created {len(created_users)} users:\n")
            for user in created_users:
                self.stdout.write(
                    f"  Username: {user['username']:<25} | Role: {user['role']:<15}"
                )
                self.stdout.write(
                    f"  Email:    {user['email']:<25} | Password: {user['password']}"
                )
                self.stdout.write("")

        if skipped_users:
            self.stdout.write(
                self.style.WARNING(f"\n⚠ Skipped {len(skipped_users)} existing users:")
            )
            for username in skipped_users:
                self.stdout.write(f"  - {username}")
            self.stdout.write(
                self.style.WARNING("Use --force flag to delete and recreate them.\n")
            )

        self.stdout.write("="*70)
        self.stdout.write(
            self.style.SUCCESS("\n✓ Injection complete! You can now login with any of the above credentials.\n")
        )
