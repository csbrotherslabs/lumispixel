from django.test import TestCase

from apps.notifications.email_delivery import queue_transactional_email


class TransactionalEmailRecipientOrderTests(TestCase):
    def test_recipient_order_is_stable(self):
        delivery = queue_transactional_email(
            event_key="studio:3:notice",
            subject="Notice",
            plain_body="Notice",
            recipients=["a@example.com", "b@example.com", "a@example.com"],
        )
        self.assertEqual(delivery.recipients, ["a@example.com", "b@example.com"])
