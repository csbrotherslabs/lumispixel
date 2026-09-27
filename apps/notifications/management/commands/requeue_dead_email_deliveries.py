from django.core.management.base import BaseCommand

from apps.notifications.models import EmailDelivery
from apps.notifications.tasks import deliver_transactional_email


class Command(BaseCommand):
    help = "Explicitly requeue dead-letter transactional emails after an operator has resolved the cause."

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, action="append", dest="ids", required=True)

    def handle(self, *args, **options):
        count = 0
        for delivery in EmailDelivery.objects.filter(pk__in=options["ids"], status=EmailDelivery.Status.DEAD):
            delivery.status = EmailDelivery.Status.PENDING
            delivery.attempt_count = 0
            delivery.failure_kind = EmailDelivery.FailureKind.NONE
            delivery.last_error = ""
            delivery.dead_at = None
            delivery.next_attempt_at = None
            delivery.save(update_fields=("status", "attempt_count", "failure_kind", "last_error", "dead_at", "next_attempt_at"))
            try:
                deliver_transactional_email.delay(delivery.pk)
            except Exception:
                # Durable pending state remains recoverable if the broker is still down.
                pass
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Requeued {count} dead-letter email delivery(s)."))
