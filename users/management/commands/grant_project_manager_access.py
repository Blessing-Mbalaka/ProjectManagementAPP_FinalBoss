from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Grant an existing account the Project Manager entitlement without replacing its primary role.'

    def add_arguments(self, parser):
        parser.add_argument('username')

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError(f"User {options['username']!r} was not found.") from exc
        group, _ = Group.objects.get_or_create(name='project_manager')
        user.groups.add(group)
        self.stdout.write(self.style.SUCCESS(
            f'Granted Project Manager access to {user.username}; primary role remains {user.role}.'
        ))
