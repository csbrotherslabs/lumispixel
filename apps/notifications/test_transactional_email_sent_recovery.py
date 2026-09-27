from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from apps.notifications.models import EmailDelivery


class TransactionalEmailSentRecoveryTests(TestCase):
    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send")
    def test_recovery_does_not_resend_sent_delivery(self, send):
        EmailDelivery.objects.create(
            idempotency_key="e" * 64,
            event_key="gallery:1:ready",
            subject="Ready",
            plain_body="Ready",
            recipients=["client@example.com"],
            status=EmailDelivery.Status.SENT,
        )
        call_command("process_transactional_email", limit=10)
        send.assert_not_called()
