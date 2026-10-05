from django.core.management.base import BaseCommand
from apps.notifications.reminders import scan_reminders


class Command(BaseCommand):
    help = 'Create due inbox reminders; safe to rerun without duplicate delivery.'

    def handle(self, *args, **options):
        scan_reminders()
        self.stdout.write(self.style.SUCCESS('Notification reminder scan completed.'))
