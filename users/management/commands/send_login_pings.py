import json

from django.core.management.base import BaseCommand, CommandError
from users.login_pings import send_login_pings


class Command(BaseCommand):
    help = 'Preview weekly login check-ins for active users; --send delivers once per account per calendar week.'

    def add_arguments(self, parser):
        parser.add_argument('--send', action='store_true', help='Send real email. Without this option, preview counts only.')

    def handle(self, *args, **options):
        try:
            result = send_login_pings(send=options['send'])
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(('SEND' if options['send'] else 'PREVIEW (no email sent)') + ': ' + json.dumps(result, sort_keys=True))
        if result['failed'] or result['uncertain']:
            raise CommandError('Delivery stopped. Review SMTP/provider logs; uncertain attempts must not be blindly resent.')
