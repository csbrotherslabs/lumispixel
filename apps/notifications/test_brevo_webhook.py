import json

from django.test import TestCase, override_settings
from django.urls import reverse

from .models import BrevoEmailEvent, EmailDelivery


@override_settings(BREVO_WEBHOOK_TOKEN="test-secret")
class BrevoWebhookTests(TestCase):
    def setUp(self):
        self.delivery = EmailDelivery.objects.create(idempotency_key="a"*64,
            event_key="test", subject="test", plain_body="test", recipients=["client@example.com"],
            status=EmailDelivery.Status.UNCERTAIN)
        self.payload = {"event": "delivered", "email": "client@example.com",
                        "message-id": "<test@brevo>", "ts_event": 1700000000,
                        "X-Mailin-custom": "lp:" + "a"*64, "id": 123}
        self.url = reverse("brevo_transactional_webhook")

    def post(self, payload, token="test-secret"):
        return self.client.post(self.url, json.dumps(payload), content_type="application/json",
                                HTTP_AUTHORIZATION="Bearer " + token)

    def test_authentication(self):
        self.assertEqual(self.post(self.payload, "wrong").status_code, 401)
        self.assertFalse(BrevoEmailEvent.objects.exists())

    def test_duplicate_and_reconciliation(self):
        self.assertEqual(self.post(self.payload).status_code, 200)
        self.assertEqual(self.post(self.payload).status_code, 200)
        self.assertEqual(BrevoEmailEvent.objects.count(), 1)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, EmailDelivery.Status.SENT)

    def test_wrong_recipient_not_correlated(self):
        self.payload["email"] = "other@example.com"
        self.assertEqual(self.post(self.payload).status_code, 200)
        self.assertIsNone(BrevoEmailEvent.objects.get().delivery_id)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, EmailDelivery.Status.UNCERTAIN)

    def test_bounce_does_not_resend(self):
        self.payload["event"] = "hard_bounce"
        self.assertEqual(self.post(self.payload).status_code, 200)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, EmailDelivery.Status.UNCERTAIN)
