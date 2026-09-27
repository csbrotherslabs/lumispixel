from django.test import TestCase

from apps.notifications.email_delivery import queue_transactional_email
from apps.notifications.models import EmailDelivery


class TransactionalEmailEventKeyTests(TestCase):
    def test_distinct_events_to_same_recipient_remain_distinct(self):
        for comment_id in (10, 11):
            queue_transactional_email(
                event_key=f"support:LP-1:reply:{comment_id}",
                subject="Support replied",
                plain_body="There is a reply",
                recipients=["client@example.com"],
            )
        self.assertEqual(EmailDelivery.objects.count(), 2)
