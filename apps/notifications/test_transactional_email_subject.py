from django.test import TestCase

from apps.notifications.email_delivery import queue_transactional_email


class TransactionalEmailSubjectTests(TestCase):
    def test_subject_is_persisted_for_deferred_delivery(self):
        delivery = queue_transactional_email(
            event_key="client:5:gallery",
            subject="Your photos are ready",
            plain_body="Ready",
            recipients=["client@example.com"],
        )
        self.assertEqual(delivery.subject, "Your photos are ready")
