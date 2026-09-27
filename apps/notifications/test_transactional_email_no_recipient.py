from django.test import TestCase

from apps.notifications.email_delivery import queue_transactional_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailNoRecipientTests(TestCase):
    def test_no_recipient_creates_no_delivery(self):
        queue_transactional_email(
            event_key="support:empty",
            subject="Nothing",
            plain_body="Nothing",
            recipients=["", None],
        )
        self.assertEqual(EmailDelivery.objects.count(), 0)
