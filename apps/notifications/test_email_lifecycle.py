from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from .models import EmailDelivery
from .email_delivery import deliver_email
from .lifecycle import cancel_queued, purge_sensitive_payloads


class EmailLifecycleTests(TestCase):
    def make(self, **kwargs):
        return EmailDelivery.objects.create(idempotency_key="a"*64, event_key="test", subject="secret",
            plain_body="token", recipients=["test@example.com"], **kwargs)

    @patch("apps.notifications.email_delivery.EmailMultiAlternatives")
    def test_expired_never_sent(self, mail):
        row = self.make(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertFalse(deliver_email(row.pk))
        row.refresh_from_db()
        self.assertEqual(row.status, "expired")
        mail.assert_not_called()

    def test_cancel_and_purge(self):
        row = self.make(sensitive=True)
        self.assertFalse(cancel_queued(delivery_id=row.pk, event_key="wrong"))
        self.assertTrue(cancel_queued(delivery_id=row.pk, event_key="test"))
        self.assertEqual(purge_sensitive_payloads(), 1)
        row.refresh_from_db()
        self.assertEqual(row.plain_body, "")
        self.assertIsNotNone(row.payload_purged_at)

    def test_inflight_not_cancelled(self):
        row = self.make(status="sending")
        self.assertFalse(cancel_queued(delivery_id=row.pk, event_key="test"))
