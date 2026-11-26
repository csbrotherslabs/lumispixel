from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import BrevoEmailEvent, EmailDelivery
from .email_monitoring import email_snapshot, delivery_rows, filtered_rows


class EmailMonitoringTests(TestCase):
    def test_counts_distinct_records_and_separate_event_window(self):
        delivery = EmailDelivery.objects.create(idempotency_key="a"*64, event_key="test",
            subject="test", plain_body="test", recipients=["a@example.com", "b@example.com"], status="sent")
        for i, event in enumerate(("delivered", "delivered", "hard_bounce")):
            BrevoEmailEvent.objects.create(fingerprint=str(i)*64, delivery=delivery, event=event,
                provider_message_id="test", recipient_hash="b"*64, occurred_at=1700000000000+i)
        BrevoEmailEvent.objects.create(fingerprint="f"*64, event="delivered",
            provider_message_id="other", recipient_hash="c"*64, occurred_at=1700000000000)
        metrics, events, _, backlog = email_snapshot(7)
        self.assertEqual(metrics["total"], 1)
        self.assertEqual(metrics["accepted"], 1)
        self.assertEqual(metrics["delivered"], 1)
        self.assertEqual(metrics["provider_failure"], 1)
        self.assertEqual(events, {"total": 4, "unmatched": 1})
        self.assertEqual(filtered_rows(delivery_rows(7), "delivered").count(), 1)
        self.assertEqual(backlog["uncertain"], 0)

    def test_old_uncertain_visible_in_backlog(self):
        delivery = EmailDelivery.objects.create(idempotency_key="a"*64, event_key="test",
            subject="test", plain_body="test", status="uncertain")
        EmailDelivery.objects.filter(pk=delivery.pk).update(created_at=timezone.now()-timedelta(days=40))
        metrics, _, _, backlog = email_snapshot(7)
        self.assertEqual(metrics["total"], 0)
        self.assertIsNone(metrics["delivery_evidence_rate"])
        self.assertEqual(backlog["uncertain"], 1)
