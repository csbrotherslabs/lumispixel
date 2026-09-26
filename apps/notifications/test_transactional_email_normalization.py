from django.test import TestCase

from apps.notifications.email_delivery import queue_transactional_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailNormalizationTests(TestCase):
    def test_recipient_case_does_not_bypass_idempotency(self):
        common = dict(event_key="account:7:changed", subject="Account changed", plain_body="Changed")
        queue_transactional_email(recipients=["Person@Example.com"], **common)
        queue_transactional_email(recipients=["person@example.com"], **common)
        self.assertEqual(EmailDelivery.objects.count(), 1)
