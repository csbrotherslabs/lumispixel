from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile

from .models import Department, EmployeeProfile, InternalRole, SupportTicket


User = get_user_model()


class SupportNotificationTests(TestCase):
    def setUp(self):
        self.support_department, _ = Department.objects.get_or_create(
            name="Customer Support", code="customer-support"
        )
        self.role = InternalRole.objects.create(
            name="Email Support Specialist",
            code="email-support-specialist",
            department=self.support_department,
        )
        self.staff_user = User.objects.create_user(
            email="email-support@lumispixel.com",
            password="test-pass-123",
            first_name="Avery",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.staff_user,
            employee_id="LP-SUP-EMAIL",
            department=self.support_department,
            role=self.role,
            status=EmployeeProfile.Status.ACTIVE,
        )
        self.customer = User.objects.create_user(
            email="support-customer@example.com",
            password="test-pass-123",
            first_name="Jordan",
            last_name="Lee",
            account_status=User.AccountStatus.ACTIVE,
            email_verified=True,
        )
        ClientProfile.objects.create(user=self.customer, display_name="Jordan Lee")

    def _ticket(self, **kwargs):
        defaults = {
            "requester": self.customer,
            "requester_type": "client",
            "category": SupportTicket.Category.TECHNICAL,
            "subject": "Support email test",
            "description": "Please help with this issue.",
            "queue": self.support_department,
        }
        defaults.update(kwargs)
        return SupportTicket.objects.create(**defaults)

    def test_ticket_creation_emails_customer_and_support_queue(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("support_help_center"),
            {
                "category": SupportTicket.Category.ACCOUNT,
                "subject": "Cannot update profile",
                "description": "The profile form will not save.",
                "related_url": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        ticket = SupportTicket.objects.get(requester=self.customer)
        self.assertEqual(len(mail.outbox), 2)
        recipients = {address for message in mail.outbox for address in message.to}
        self.assertIn(self.customer.email, recipients)
        self.assertIn(self.staff_user.email, recipients)
        self.assertTrue(any(ticket.reference in message.subject for message in mail.outbox))

    def test_customer_reply_notifies_assignee(self):
        ticket = self._ticket(assignee=self.employee, status=SupportTicket.Status.WAITING_CUSTOMER)
        self.client.force_login(self.customer)
        mail.outbox.clear()
        response = self.client.post(
            reverse("support_ticket_detail", args=[ticket.reference]),
            {"body": "I tried the suggested step and still need help."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.staff_user.email])
        self.assertIn("Customer replied", mail.outbox[0].subject)

    def test_staff_public_reply_notifies_customer(self):
        ticket = self._ticket(assignee=self.employee)
        self.client.force_login(self.staff_user)
        mail.outbox.clear()
        response = self.client.post(
            reverse("internal_ops:ticket_detail", args=[ticket.reference]),
            {"action": "reply", "body": "We have a fix ready. Please try again."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.customer.email])
        self.assertIn("LumisPixel Support replied", mail.outbox[0].subject)

    def test_internal_note_does_not_send_customer_email(self):
        ticket = self._ticket(assignee=self.employee)
        self.client.force_login(self.staff_user)
        mail.outbox.clear()
        response = self.client.post(
            reverse("internal_ops:ticket_detail", args=[ticket.reference]),
            {"action": "note", "body": "Private investigation details."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_status_change_and_assignment_send_targeted_emails(self):
        ticket = self._ticket()
        self.client.force_login(self.staff_user)
        mail.outbox.clear()
        response = self.client.post(
            reverse("internal_ops:ticket_detail", args=[ticket.reference]),
            {
                "action": "update",
                "status": SupportTicket.Status.IN_PROGRESS,
                "priority": SupportTicket.Priority.HIGH,
                "queue": str(self.support_department.pk),
                "assignee": str(self.employee.pk),
                "due_at": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)
        recipients = [message.to for message in mail.outbox]
        self.assertIn([self.customer.email], recipients)
        self.assertIn([self.staff_user.email], recipients)

    @patch("apps.internal_ops.support_notifications.EmailMultiAlternatives.send", side_effect=RuntimeError("mail unavailable"))
    def test_email_failure_does_not_block_ticket_creation(self, _send):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("support_help_center"),
            {
                "category": SupportTicket.Category.OTHER,
                "subject": "Mail outage should not block support",
                "description": "Ticket must still be saved.",
                "related_url": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            SupportTicket.objects.filter(
                requester=self.customer,
                subject="Mail outage should not block support",
            ).exists()
        )
