from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from apps.notifications.models import EmailDelivery
from apps.notifications.lifecycle import eligible
from apps.notifications.payload_crypto import decrypt_payload


@override_settings(PUBLIC_BASE_URL="https://lumispixel.example", EMAIL_PAYLOAD_KEYS=Fernet.generate_key().decode())
class DurablePasswordResetTests(TestCase):
    def test_reset_is_encrypted_and_password_change_invalidates_queue(self):
        User = get_user_model()
        user = User.objects.create_user(email="reset@example.com", password="original-password-123")
        response = self.client.post(reverse("accounts:password-reset"), {"email": user.email})
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        row = EmailDelivery.objects.get(lifecycle_kind="account.password_reset")
        self.assertEqual(row.plain_body, "")
        self.assertTrue(row.encrypted_payload)
        self.assertIn("lumispixel.example", decrypt_payload(row)[1])
        self.assertTrue(eligible(row))
        user.set_password("changed-password-123")
        user.save(update_fields=["password"])
        self.assertFalse(eligible(row))

    def test_unknown_email_same_redirect(self):
        response = self.client.post(reverse("accounts:password-reset"), {"email": "missing@example.com"})
        self.assertRedirects(response, reverse("accounts:password-reset-done"))
        self.assertFalse(EmailDelivery.objects.filter(lifecycle_kind="account.password_reset").exists())
