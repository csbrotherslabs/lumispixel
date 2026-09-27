import smtplib
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .email_delivery import MAX_DELIVERY_ATTEMPTS, deliver_email, queue_transactional_email, record_failure
from .models import EmailDelivery


class DeliveryReliabilityTests(TestCase):
    def make_delivery(self, event="p2:test"):
        return queue_transactional_email(event_key=event, subject="Test", plain_body="Body", recipients=["USER@example.com"])

    def test_idempotency_survives_repeated_queueing(self):
        first = self.make_delivery()
        second = self.make_delivery()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(EmailDelivery.objects.count(), 1)

    def test_421_is_transient_and_schedules_retry(self):
        delivery = self.make_delivery("p2:421")
        delivery.attempt_count = 1
        delivery.save(update_fields=("attempt_count",))
        record_failure(delivery.pk, smtplib.SMTPResponseException(421, b"provider unavailable"))
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDelivery.Status.RETRY)
        self.assertEqual(delivery.failure_kind, EmailDelivery.FailureKind.TRANSIENT)
        self.assertIsNotNone(delivery.next_attempt_at)

    def test_550_is_permanent_and_dead_letters_immediately(self):
        delivery = self.make_delivery("p2:550")
        record_failure(delivery.pk, smtplib.SMTPResponseException(550, b"mailbox unavailable"))
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDelivery.Status.DEAD)
        self.assertEqual(delivery.failure_kind, EmailDelivery.FailureKind.PERMANENT)
        self.assertIsNotNone(delivery.dead_at)

    def test_retry_budget_exhaustion_dead_letters_poison_message(self):
        delivery = self.make_delivery("p2:poison")
        delivery.attempt_count = MAX_DELIVERY_ATTEMPTS
        delivery.save(update_fields=("attempt_count",))
        record_failure(delivery.pk, TimeoutError("provider timeout"))
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDelivery.Status.DEAD)

    @patch("apps.notifications.email_delivery.EmailMultiAlternatives.send", return_value=1)
    def test_sent_delivery_is_not_sent_twice(self, send):
        delivery = self.make_delivery("p2:duplicate")
        self.assertTrue(deliver_email(delivery.pk))
        self.assertFalse(deliver_email(delivery.pk))
        self.assertEqual(send.call_count, 1)

    @patch("apps.notifications.tasks.deliver_transactional_email.delay")
    def test_reconciliation_only_enqueues_due_retries(self, delay):
        from .tasks import reconcile_pending_transactional_emails
        due = self.make_delivery("p2:due")
        due.status = EmailDelivery.Status.RETRY
        due.next_attempt_at = timezone.now() - timedelta(seconds=1)
        due.save(update_fields=("status", "next_attempt_at"))
        future = self.make_delivery("p2:future")
        future.status = EmailDelivery.Status.RETRY
        future.next_attempt_at = timezone.now() + timedelta(hours=1)
        future.save(update_fields=("status", "next_attempt_at"))
        reconcile_pending_transactional_emails()
        delay.assert_called_once_with(due.pk)
