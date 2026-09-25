from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.internal_ops.models import SupportTicket, SupportTicketAttachment, SupportTicketComment


class SupportFailureIsolationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reliability-support@example.com",
            password="testpass",
        )
        self.client.force_login(self.user)

    @patch("apps.core.support_views.create_support_attachment", side_effect=RuntimeError("storage unavailable"))
    def test_ticket_and_attachment_write_roll_back_together(self, _create_attachment):
        response = self.client.post(
            reverse("core:help_center") if False else "/resources/help-center/",
            {
                "subject": "Atomic support ticket",
                "category": "technical",
                "description": "Attachment storage should not leave a partial ticket.",
                "attachment": SimpleUploadedFile("evidence.txt", b"evidence"),
            },
        )
        self.assertEqual(response.status_code, 500)
        self.assertFalse(SupportTicket.objects.filter(subject="Atomic support ticket").exists())

    @patch("apps.core.support_views.notify_ticket_created", side_effect=RuntimeError("mail unavailable"))
    def test_notification_failure_occurs_after_ticket_commit(self, _notify):
        try:
            self.client.post(
                "/resources/help-center/",
                {
                    "subject": "Persist before notification",
                    "category": "technical",
                    "description": "The ticket remains authoritative.",
                },
            )
        except RuntimeError:
            pass
        self.assertTrue(SupportTicket.objects.filter(subject="Persist before notification").exists())
