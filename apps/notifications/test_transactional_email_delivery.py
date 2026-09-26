from unittest.mock import patch

from django.test import TestCase, TransactionTestCase

from apps.notifications.email_delivery import deliver_email, queue_transactional_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailQueueTests(TestCase):
    def test_duplicate_event_creates_one_delivery(self):
        first = queue_transactional_email(
            event_key="gallery:42:published",
            subject="Gallery ready",
            plain_body="Ready",
            recipients=["client@example.com"],
        )
        second = queue_transactional_email(
            event_key="gallery:42:published",
            subject="Gallery ready",
            plain_body="Ready",
            recipients=["client@example.com"],
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(EmailDelivery.objects.count(), 1)

    def test_rollback_does_not_dispatch(self):
        with patch("apps.notifications.tasks.deliver_transactional_email.delay") as delay:
            try:
                with self.captureOnCommitCallbacks(execute=False):
                    from django.db import transaction
                    with transaction.atomic():
                        queue_transactional_email(
                            event_key="booking:9:created",
                            subject="Booking received",
                            plain_body="Received",
                            recipients=["client@example.com"],
                        )
                        raise RuntimeError("rollback")
            except RuntimeError:
                pass
            delay.assert_not_called()


class TransactionalEmailDeliveryTests(TransactionTestCase):
    def setUp(self):
        self.delivery = EmailDelivery.objects.create(
            idempotency_key="a" * 64,
            event_key="account:1:changed",
            subject="Account changed",
            plain_body="Changed",
            recipients=["person@example.com"],
        )

    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", return_value=1)
    def test_success_marks_sent_and_replay_does_not_send_twice(self, send):
        self.assertTrue(deliver_email(self.delivery.pk))
        self.assertFalse(deliver_email(self.delivery.pk))
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, EmailDelivery.Status.SENT)
        self.assertEqual(send.call_count, 1)

    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", side_effect=RuntimeError("smtp down"))
    def test_smtp_failure_is_scheduled_for_retry(self, send):
        with self.assertRaises(RuntimeError):
            deliver_email(self.delivery.pk)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, EmailDelivery.Status.RETRY)
        self.assertEqual(self.delivery.attempt_count, 1)
        self.assertIsNotNone(self.delivery.next_attempt_at)
        self.assertIn("smtp down", self.delivery.last_error)
