from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.test import TestCase, override_settings

from apps.notifications.email_delivery import (
    normalize_recipients,
    public_url,
    queue_transactional_email,
    safe_html_text,
)
from apps.notifications.models import EmailDelivery


class NotificationSecurityContentTests(TestCase):
    def test_recipient_normalization_deduplicates_case_insensitively(self):
        recipients = normalize_recipients([" Client@Example.com ", "client@example.com"])
        self.assertEqual(recipients, ("Client@Example.com",))

    def test_recipient_header_injection_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_recipients(["victim@example.com\nBcc: attacker@example.com"])

    def test_invalid_recipient_is_rejected(self):
        with self.assertRaises(ValidationError):
            normalize_recipients(["not-an-email"])

    def test_subject_header_injection_is_rejected(self):
        with self.assertRaises(ValueError):
            queue_transactional_email(
                event_key="security:subject",
                subject="Hello\nBcc: attacker@example.com",
                plain_body="body",
                recipients=["client@example.com"],
            )
        self.assertFalse(EmailDelivery.objects.exists())

    @override_settings(DEBUG=False, PUBLIC_BASE_URL="https://lumispixel.com")
    def test_public_url_uses_configured_origin(self):
        self.assertEqual(public_url("/account/settings/"), "https://lumispixel.com/account/settings/")

    @override_settings(DEBUG=False, PUBLIC_BASE_URL="http://lumispixel.com")
    def test_production_public_url_rejects_http(self):
        with self.assertRaises(ImproperlyConfigured):
            public_url("/reset/")

    @override_settings(DEBUG=False, PUBLIC_BASE_URL="https://user:pass@lumispixel.com")
    def test_public_url_rejects_credentials_in_origin(self):
        with self.assertRaises(ImproperlyConfigured):
            public_url("/reset/")

    def test_html_user_content_is_escaped(self):
        rendered = safe_html_text('<img src=x onerror="alert(1)"> & client')
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img", rendered)
        self.assertIn("&amp; client", rendered)

    @patch("apps.notifications.email_delivery.EmailMultiAlternatives")
    def test_delivery_uses_to_only_without_cc_or_bcc(self, message_cls):
        delivery = EmailDelivery.objects.create(
            idempotency_key="e" * 64,
            event_key="tenant:1:event:1",
            subject="Private update",
            plain_body="Private",
            recipients=["one@example.com"],
        )
        message_cls.return_value.send.return_value = 1
        from apps.notifications.email_delivery import deliver_email
        deliver_email(delivery.pk)
        kwargs = message_cls.call_args.kwargs
        self.assertEqual(kwargs["to"], ["one@example.com"])
        self.assertNotIn("cc", kwargs)
        self.assertNotIn("bcc", kwargs)
