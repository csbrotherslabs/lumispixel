from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.notifications.models import EmailDelivery


class Command(BaseCommand):
    help = "Report transactional email queue health for reconciliation/operations."

    def handle(self, *args, **options):
        counts = {row["status"]: row["count"] for row in EmailDelivery.objects.values("status").annotate(count=Count("id"))}
        for status in (EmailDelivery.Status.PENDING, EmailDelivery.Status.RETRY, EmailDelivery.Status.SENT, EmailDelivery.Status.DEAD, EmailDelivery.Status.FAILED):
            self.stdout.write(f"{status}: {counts.get(status, 0)}")
