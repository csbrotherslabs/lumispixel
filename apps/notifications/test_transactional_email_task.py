import smtplib
from unittest.mock import patch

from django.test import TestCase

from apps.notifications.models import EmailDelivery
from apps.notifications.tasks import deliver_transactional_email


class TransactionalEmailTaskTests(TestCase):
    def setUp(self):
        self.delivery = EmailDelivery.objects.create(
            idempotency_key="b" * 64,
            event_key="support:1:reply:2",
            subject="Support replied",
            plain_body="Reply",
            recipients=["client@example.com"],
        )

    @patch("apps.notifications.tasks.deliver_email", side_effect=RuntimeError("unexpected failure"))
    def test_task_does_not_invent_attempt_before_claim(self, deliver):
        self.assertFalse(deliver_transactional_email.apply(args=[self.delivery.pk], throw=True).get())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, EmailDelivery.Status.PENDING)
        self.assertEqual(self.delivery.attempt_count, 0)
        self.assertFalse(self.delivery.last_error)

    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", side_effect=smtplib.SMTPDataError(451, b"temporary rejection"))
    @patch("apps.notifications.tasks.deliver_transactional_email.retry")
    def test_task_records_definitive_failure_before_retry(self, retry, send):
        from celery.exceptions import Retry
        retry.side_effect = Retry()
        with self.assertRaises(Retry):
            deliver_transactional_email.run(self.delivery.pk)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, EmailDelivery.Status.RETRY)
        self.assertEqual(self.delivery.last_error, "SMTPDataError")
        self.assertEqual(self.delivery.failure_kind, EmailDelivery.FailureKind.TRANSIENT)
        self.assertIsNotNone(self.delivery.next_attempt_at)
        retry.assert_called_once()
