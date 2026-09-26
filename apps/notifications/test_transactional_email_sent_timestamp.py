from unittest.mock import patch

from django.test import TransactionTestCase

from apps.notifications.email_delivery import deliver_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailSentTimestampTests(TransactionTestCase):
    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", return_value=1)
    def test_success_records_sent_timestamp(self, send):
        delivery = EmailDelivery.objects.create(
            idempotency_key="1" * 64,
            event_key="gallery:44:ready",
            subject="Ready",
            plain_body="Ready",
            recipients=["client@example.com"],
        )
        deliver_email(delivery.pk)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.sent_at)
