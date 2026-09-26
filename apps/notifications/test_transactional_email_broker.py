from unittest.mock import patch

from django.test import TransactionTestCase

from apps.notifications.email_delivery import queue_transactional_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailBrokerIsolationTests(TransactionTestCase):
    @patch("apps.notifications.tasks.deliver_transactional_email.delay", side_effect=RuntimeError("broker down"))
    def test_broker_outage_does_not_fail_committed_operation(self, delay):
        delivery = queue_transactional_email(
            event_key="gallery:77:delivered",
            subject="Your gallery is ready",
            plain_body="Ready",
            recipients=["client@example.com"],
        )
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, EmailDelivery.Status.PENDING)
        self.assertEqual(EmailDelivery.objects.count(), 1)
