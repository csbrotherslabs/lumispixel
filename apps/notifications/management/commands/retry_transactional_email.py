from django.core.management.base import BaseCommand

from apps.notifications.models import EmailDelivery
from apps.notifications.tasks import deliver_transactional_email


class Command(BaseCommand):
    help = "Re-enqueue pending transactional emails after SMTP or broker outages."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        ids = list(
            EmailDelivery.objects.filter(status=EmailDelivery.Status.PENDING)
            .order_by("created_at")
            .values_list("pk", flat=True)[: options["limit"]]
        )
        queued = 0
        for delivery_id in ids:
            try:
                deliver_transactional_email.delay(delivery_id)
                queued += 1
            except Exception as exc:
                self.stderr.write(f"Could not enqueue {delivery_id}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Queued {queued} pending transactional emails."))
