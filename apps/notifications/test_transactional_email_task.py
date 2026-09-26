from unittest.mock import patch

from django.test import TestCase

from apps.notifications.models import EmailDelivery
from apps.notifications.tasks import deliver_transactional_email


class TransactionalEmailTaskTests(TestCase):
    def setUp(self):
        self.delivery = EmailDelivery.objects.create(
            idempotency_key="b" * 64,
            event_key="support:1:reply:2",
            subject="Support replied",
            plain_body="Reply",
            recipients=["client@example.com"],
        )

    @patch("apps.notifications.tasks.deliver_email", side_effect=RuntimeError("smtp unavailable"))
    def test_task_records_error_before_retry(self, deliver):
        with self.assertRaises(Exception):
            deliver_transactional_email.apply(args=[self.delivery.pk], throw=True)
        self.delivery.refresh_from_db()
        self.assertIn("smtp unavailable", self.delivery.last_error)
        self.assertEqual(self.delivery.status, EmailDelivery.Status.PENDING)
