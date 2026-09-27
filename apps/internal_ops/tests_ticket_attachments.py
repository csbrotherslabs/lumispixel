import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import ClientProfile

from .models import Department, EmployeeProfile, InternalRole, SupportTicket, SupportTicketAttachment


User = get_user_model()
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="lumispixel-support-tests-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class SupportTicketAttachmentTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.department, _ = Department.objects.get_or_create(name="Customer Support", code="customer-support")
        role = InternalRole.objects.create(name="Attachment Support", code="attachment-support", department=self.department)
        self.staff_user = User.objects.create_user(
            email="attachment-support@lumispixel.com", password="test-pass-123", first_name="Avery",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.staff_user, employee_id="LP-ATT-001", department=self.department,
            role=role, status=EmployeeProfile.Status.ACTIVE,
        )
        self.customer = User.objects.create_user(
            email="attachment-client@example.com", password="test-pass-123", first_name="Jordan",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )
        ClientProfile.objects.create(user=self.customer, display_name="Jordan")
        self.other_customer = User.objects.create_user(
            email="other-client@example.com", password="test-pass-123", first_name="Taylor",
            account_status=User.AccountStatus.ACTIVE, email_verified=True,
        )
        ClientProfile.objects.create(user=self.other_customer, display_name="Taylor")

    def _ticket(self):
        return SupportTicket.objects.create(
            requester=self.customer, requester_type="client", category=SupportTicket.Category.TECHNICAL,
            subject="Attachment test", description="Need help", queue=self.department,
        )

    def test_customer_can_attach_file_when_opening_ticket(self):
        self.client.force_login(self.customer)
        upload = SimpleUploadedFile("screenshot.png", b"fake-png-content", content_type="image/png")
        response = self.client.post(reverse("support_help_center"), {
            "category": SupportTicket.Category.TECHNICAL,
            "subject": "Screenshot included",
            "description": "See the attached screenshot.",
            "related_url": "",
            "attachment": upload,
        })
        self.assertEqual(response.status_code, 302)
        ticket = SupportTicket.objects.get(requester=self.customer)
        attachment = SupportTicketAttachment.objects.get(ticket=ticket)
        self.assertEqual(attachment.original_name, "screenshot.png")
        self.assertFalse(attachment.is_internal)
        self.assertEqual(attachment.uploaded_by_user, self.customer)

    def test_customer_reply_attachment_is_visible_and_secure(self):
        ticket = self._ticket()
        self.client.force_login(self.customer)
        upload = SimpleUploadedFile("details.pdf", b"pdf-data", content_type="application/pdf")
        self.client.post(reverse("support_ticket_detail", args=[ticket.reference]), {
            "body": "More details attached.",
            "attachment": upload,
        })
        attachment = SupportTicketAttachment.objects.get(ticket=ticket)
        page = self.client.get(reverse("support_ticket_detail", args=[ticket.reference]))
        self.assertContains(page, "details.pdf")
        download_url = reverse("support_attachment_download", args=[ticket.reference, attachment.pk])
        self.assertEqual(self.client.get(download_url).status_code, 200)

        self.client.force_login(self.other_customer)
        self.assertEqual(self.client.get(download_url).status_code, 404)

    def test_internal_note_attachment_is_hidden_from_customer(self):
        ticket = self._ticket()
        self.client.force_login(self.staff_user)
        upload = SimpleUploadedFile("investigation.log", b"private-log", content_type="text/plain")
        self.client.post(reverse("internal_ops:ticket_detail", args=[ticket.reference]), {
            "action": "note",
            "body": "Internal investigation",
            "attachment": upload,
        })
        attachment = SupportTicketAttachment.objects.get(ticket=ticket)
        self.assertTrue(attachment.is_internal)
        self.assertEqual(attachment.uploaded_by_employee, self.employee)

        self.client.force_login(self.customer)
        customer_page = self.client.get(reverse("support_ticket_detail", args=[ticket.reference]))
        self.assertNotContains(customer_page, "investigation.log")
        download_url = reverse("support_attachment_download", args=[ticket.reference, attachment.pk])
        self.assertEqual(self.client.get(download_url).status_code, 404)

    def test_staff_public_attachment_is_available_to_ticket_owner(self):
        ticket = self._ticket()
        self.client.force_login(self.staff_user)
        upload = SimpleUploadedFile("resolution.pdf", b"resolution-data", content_type="application/pdf")
        self.client.post(reverse("internal_ops:ticket_detail", args=[ticket.reference]), {
            "action": "reply",
            "body": "Please review this document.",
            "attachment": upload,
        })
        attachment = SupportTicketAttachment.objects.get(ticket=ticket)
        self.assertFalse(attachment.is_internal)

        self.client.force_login(self.customer)
        page = self.client.get(reverse("support_ticket_detail", args=[ticket.reference]))
        self.assertContains(page, "resolution.pdf")
        self.assertEqual(
            self.client.get(reverse("support_attachment_download", args=[ticket.reference, attachment.pk])).status_code,
            200,
        )

    def test_unsupported_attachment_type_is_rejected(self):
        self.client.force_login(self.customer)
        upload = SimpleUploadedFile("script.exe", b"unsafe", content_type="application/octet-stream")
        response = self.client.post(reverse("support_help_center"), {
            "category": SupportTicket.Category.TECHNICAL,
            "subject": "Bad file",
            "description": "Testing invalid attachment.",
            "related_url": "",
            "attachment": upload,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unsupported attachment type")
        self.assertFalse(SupportTicket.objects.filter(requester=self.customer).exists())
