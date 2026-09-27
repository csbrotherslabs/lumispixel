from django.test import TestCase

from apps.notifications.email_delivery import queue_transactional_email


class TransactionalEmailRecipientTests(TestCase):
    def test_empty_recipient_list_is_ignored(self):
        self.assertIsNone(
            queue_transactional_email(
                event_key="system:no-recipient",
                subject="Ignored",
                plain_body="Ignored",
                recipients=[],
            )
        )

    def test_duplicate_recipients_are_collapsed(self):
        delivery = queue_transactional_email(
            event_key="account:4:security",
            subject="Security notice",
            plain_body="Notice",
            recipients=["person@example.com", "person@example.com"],
        )
        self.assertEqual(delivery.recipients, ["person@example.com"])
