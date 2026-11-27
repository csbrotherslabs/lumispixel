from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from .intents import require_email, missing_intents
from .models import EmailIntent, EmailDelivery
from .email_delivery import queue_transactional_email
from .retention import purge_old_terminal_payloads

class EmailIntentTests(TestCase):
    def test_independent_intent_links_to_delivery(self):
        intent = require_email(event_key="test:1", recipients=["a@example.com"])
        delivery = queue_transactional_email(event_key="test:1", recipients=["a@example.com"], subject="Test", plain_body="Body")
        intent.refresh_from_db()
        self.assertEqual(intent.delivery_id, delivery.pk)
        self.assertEqual(EmailIntent.objects.count(), 1)

    def test_missing_intent_and_policy_mismatch(self):
        intent = require_email(event_key="test:2", recipients=["a@example.com"], kind="test")
        EmailIntent.objects.filter(pk=intent.pk).update(created_at=timezone.now()-timedelta(minutes=16))
        self.assertTrue(missing_intents().filter(pk=intent.pk).exists())
        with self.assertRaises(ValidationError):
            require_email(event_key="test:2", recipients=["a@example.com"], kind="different")

    @override_settings(EMAIL_TERMINAL_PAYLOAD_RETENTION_DAYS=30)
    def test_retention_preserves_delivery_record(self):
        row = queue_transactional_email(event_key="test:3", recipients=["a@example.com"], subject="Test", plain_body="Body")
        EmailDelivery.objects.filter(pk=row.pk).update(status="sent", sent_at=timezone.now()-timedelta(days=31))
        self.assertEqual(purge_old_terminal_payloads(), 1)
        row.refresh_from_db()
        self.assertEqual(row.plain_body, "")
        self.assertTrue(row.payload_purged_at)
        self.assertEqual(row.intent.delivery_id, row.pk)
