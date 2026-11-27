from datetime import timedelta
from cryptography.fernet import Fernet
from django.test import TestCase, override_settings
from django.utils import timezone
from .email_delivery import queue_transactional_email
from .payload_crypto import decrypt_payload


class PayloadTests(TestCase):
    def test_encryption_rotation_and_supersession(self):
        old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
        def enqueue(event):
            return queue_transactional_email(event_key=event, subject="private subject",
                plain_body="private token", recipients=["a@example.com"], sensitive=True,
                expires_at=timezone.now()+timedelta(hours=1), lifecycle_kind="account.verify",
                supersession_scope="account.verify:1")
        with override_settings(EMAIL_PAYLOAD_KEYS=old):
            first = enqueue("first")
        self.assertEqual(first.plain_body, "")
        self.assertNotIn("private token", first.encrypted_payload)
        with override_settings(EMAIL_PAYLOAD_KEYS=new+","+old):
            self.assertEqual(decrypt_payload(first)[1], "private token")
            second = enqueue("second")
            self.assertEqual(enqueue("first").pk, first.pk)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.status, "cancelled")
        self.assertEqual(second.status, "pending")
