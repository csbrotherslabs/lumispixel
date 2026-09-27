from unittest.mock import patch

from django.test import TransactionTestCase

from apps.notifications.email_delivery import queue_transactional_email


class TransactionalEmailCommitTests(TransactionTestCase):
    @patch("apps.notifications.tasks.deliver_transactional_email.delay")
    def test_dispatch_occurs_after_commit(self, delay):
        delivery = queue_transactional_email(
            event_key="booking:11:confirmed",
            subject="Booking confirmed",
            plain_body="Confirmed",
            recipients=["client@example.com"],
        )
        delay.assert_called_once_with(delivery.pk)
