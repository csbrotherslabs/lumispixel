from unittest.mock import patch

from django.test import TransactionTestCase

from apps.notifications.email_delivery import deliver_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailAttemptTimestampTests(TransactionTestCase):
    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", side_effect=RuntimeError("down"))
    def test_failed_attempt_records_timestamp(self, send):
        delivery = EmailDelivery.objects.create(
            idempotency_key="f" * 64,
            event_key="booking:30:reminder",
            subject="Reminder",
            plain_body="Reminder",
            recipients=["client@example.com"],
        )
        with self.assertRaises(RuntimeError):
            deliver_email(delivery.pk)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.last_attempt_at)
