from unittest.mock import patch

from django.test import TransactionTestCase

from apps.notifications.email_delivery import deliver_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailFailureBudgetTests(TransactionTestCase):
    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", side_effect=RuntimeError("smtp down"))
    def test_each_failed_attempt_is_counted(self, send):
        delivery = EmailDelivery.objects.create(
            idempotency_key="d" * 64,
            event_key="support:2:created",
            subject="Support request",
            plain_body="Created",
            recipients=["client@example.com"],
        )
        for expected in (1, 2):
            with self.assertRaises(RuntimeError):
                deliver_email(delivery.pk)
            delivery.refresh_from_db()
            self.assertEqual(delivery.attempt_count, expected)
            self.assertEqual(delivery.status, EmailDelivery.Status.PENDING)
