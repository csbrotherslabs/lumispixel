from django.core.management.base import BaseCommand

from apps.notifications.email_delivery import deliver_email
from apps.notifications.models import EmailDelivery


class Command(BaseCommand):
    help = "Synchronously process pending transactional email outbox rows."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        ids = list(
            EmailDelivery.objects.filter(status=EmailDelivery.Status.PENDING)
            .order_by("created_at")
            .values_list("pk", flat=True)[: options["limit"]]
        )
        sent = 0
        failed = 0
        for delivery_id in ids:
            try:
                sent += int(bool(deliver_email(delivery_id)))
            except Exception as exc:
                failed += 1
                EmailDelivery.objects.filter(pk=delivery_id).update(last_error=str(exc)[:2000])
        self.stdout.write(f"Processed {len(ids)} pending emails: sent={sent}, failed={failed}.")
