import smtplib
from unittest.mock import patch

from django.test import TransactionTestCase
from django.utils import timezone

from apps.notifications.email_delivery import deliver_email
from apps.notifications.models import EmailDelivery, EmailAttempt


class TransactionalEmailFailureBudgetTests(TransactionTestCase):
    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", side_effect=smtplib.SMTPDataError(451, b"temporary rejection"))
    def test_each_failed_attempt_is_counted(self, send):
        delivery = EmailDelivery.objects.create(
            idempotency_key="d" * 64,
            event_key="support:2:created",
            subject="Support request",
            plain_body="Created",
            recipients=["client@example.com"],
        )
        for expected in (1, 2):
            with self.assertRaises(smtplib.SMTPDataError):
                deliver_email(delivery.pk)
            delivery.refresh_from_db()
            self.assertEqual(delivery.attempt_count, expected)
            self.assertEqual(delivery.status, EmailDelivery.Status.RETRY)
            self.assertIsNotNone(delivery.next_attempt_at)
            # Simulate the scheduled retry becoming due without sleeping in the test.
            EmailDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now())
        self.assertEqual(list(EmailAttempt.objects.filter(delivery=delivery).order_by("number").values_list("number", "outcome")), [(1, "retry"), (2, "retry")])
