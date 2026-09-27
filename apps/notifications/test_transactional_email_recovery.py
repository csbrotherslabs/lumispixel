from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.notifications.models import EmailDelivery


class TransactionalEmailRecoveryTests(TestCase):
    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", return_value=1)
    def test_process_command_recovers_pending_delivery(self, send):
        delivery = EmailDelivery.objects.create(
            idempotency_key="c" * 64,
            event_key="gallery:8:ready",
            subject="Gallery ready",
            plain_body="Ready",
            recipients=["client@example.com"],
        )
        call_command("process_transactional_email", limit=10)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDelivery.Status.SENT)
        self.assertEqual(send.call_count, 1)
