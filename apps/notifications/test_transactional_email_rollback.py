from unittest.mock import patch

from django.db import transaction
from django.test import TransactionTestCase

from apps.notifications.email_delivery import queue_transactional_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailRollbackTests(TransactionTestCase):
    @patch("apps.notifications.tasks.deliver_transactional_email.delay")
    def test_database_rollback_removes_outbox_and_never_dispatches(self, delay):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                queue_transactional_email(
                    event_key="booking:99:created",
                    subject="Booking received",
                    plain_body="Received",
                    recipients=["client@example.com"],
                )
                raise RuntimeError("force rollback")
        self.assertFalse(EmailDelivery.objects.exists())
        delay.assert_not_called()
