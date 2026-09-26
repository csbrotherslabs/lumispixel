from django.test import TestCase

from apps.notifications.email_delivery import queue_transactional_email


class TransactionalEmailPayloadTests(TestCase):
    def test_outbox_preserves_html_and_plain_payload(self):
        delivery = queue_transactional_email(
            event_key="booking:22:updated",
            subject="Booking updated",
            plain_body="Plain update",
            html_body="<strong>Update</strong>",
            recipients=["client@example.com"],
        )
        self.assertEqual(delivery.plain_body, "Plain update")
        self.assertEqual(delivery.html_body, "<strong>Update</strong>")
