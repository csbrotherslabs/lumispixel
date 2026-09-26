from django.test import TestCase

from apps.notifications.email_delivery import queue_transactional_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailStatusTests(TestCase):
    def test_new_delivery_starts_pending(self):
        delivery = queue_transactional_email(
            event_key="account:8:welcome",
            subject="Welcome",
            plain_body="Welcome",
            recipients=["person@example.com"],
        )
        self.assertEqual(delivery.status, EmailDelivery.Status.PENDING)
