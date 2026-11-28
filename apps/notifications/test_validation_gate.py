from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import EmailDelivery, EmailAttempt
from .email_delivery import deliver_email, record_failure, retry_delay
from .brevo_transport import ProviderUncertain

@override_settings(TRANSACTIONAL_EMAIL_TRANSPORT="brevo", BREVO_API_KEY="mock-only")
class TransportValidationTests(TestCase):
    def row(self):
        return EmailDelivery.objects.create(idempotency_key="b"*64, event_key="validation:1",
            subject="Test", plain_body="Test", recipients=["client@example.com"])

    @patch("apps.notifications.email_delivery.EmailMultiAlternatives")
    @patch("apps.notifications.brevo_transport.submit", side_effect=ProviderUncertain)
    def test_uncertain_no_fallback_or_replay(self, submit, smtp):
        row = self.row()
        with self.assertRaises(ProviderUncertain):
            deliver_email(row.pk)
        row.refresh_from_db()
        self.assertEqual(row.status, EmailDelivery.Status.UNCERTAIN)
        self.assertFalse(deliver_email(row.pk))
        self.assertEqual(submit.call_count, 1)
        smtp.assert_not_called()

    def test_stale_attempt_cannot_mutate_current_claim(self):
        row = self.row()
        EmailDelivery.objects.filter(pk=row.pk).update(status="sending", attempt_count=2)
        record_failure(row.pk, ProviderUncertain(), attempt_number=1)
        row.refresh_from_db()
        self.assertEqual(row.status, "sending")

    @patch("apps.notifications.brevo_transport.submit", return_value="<mock@example.com>")
    def test_acceptance_persists_attempt(self, submit):
        row = self.row()
        self.assertTrue(deliver_email(row.pk))
        attempt = EmailAttempt.objects.get(delivery=row)
        self.assertEqual(attempt.provider_message_id, "<mock@example.com>")
        self.assertEqual(attempt.transport, "brevo")
        self.assertEqual(attempt.outcome, "sent")

    def test_retry_delay_bounded(self):
        self.assertEqual(retry_delay(100000), 3600)
