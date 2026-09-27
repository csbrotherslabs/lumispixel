from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ClientProfile, PhotographerProfile

from .models import Department, EmployeeProfile, InternalAuditEvent, InternalRole, SupportTicket, SupportTicketComment


User = get_user_model()


class SupportTicketingTests(TestCase):
    def setUp(self):
        self.support_department, _ = Department.objects.get_or_create(name="Customer Support", code="customer-support")
        self.role = InternalRole.objects.create(name="Support Specialist", code="support-specialist-ticketing", department=self.support_department)
        self.staff_user = User.objects.create_user(email="support-tickets@lumispixel.com", password="test-pass-123", first_name="Avery", account_status=User.AccountStatus.ACTIVE, email_verified=True)
        self.employee = EmployeeProfile.objects.create(user=self.staff_user, employee_id="LP-SUP-100", department=self.support_department, role=self.role, status=EmployeeProfile.Status.ACTIVE)
        self.client_user = User.objects.create_user(email="client-ticket@example.com", password="test-pass-123", first_name="Jordan", last_name="Lee", account_status=User.AccountStatus.ACTIVE, email_verified=True)
        ClientProfile.objects.create(user=self.client_user, display_name="Jordan Lee")
        self.photographer_user = User.objects.create_user(email="studio-ticket@example.com", password="test-pass-123", first_name="Morgan", last_name="Reed", primary_role=User.PrimaryRole.PHOTOGRAPHER, account_status=User.AccountStatus.ACTIVE, email_verified=True)
        PhotographerProfile.objects.create(user=self.photographer_user, display_name="Morgan Reed", business_name="North Light Studio", slug="north-light-support")

    def test_help_center_is_public_but_requires_sign_in_to_submit(self):
        response = self.client.get(reverse("support_help_center"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How can we help?")
        self.assertContains(response, "Sign in to contact support")
        response = self.client.post(reverse("support_help_center"), {"category": SupportTicket.Category.ACCOUNT, "subject": "Cannot access account", "description": "I cannot sign in.", "related_url": ""})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SupportTicket.objects.count(), 0)

    def test_client_can_submit_ticket_from_help_center(self):
        self.client.force_login(self.client_user)
        response = self.client.post(reverse("support_help_center"), {"category": SupportTicket.Category.CLIENT_ACCESS, "subject": "Gallery access issue", "description": "My gallery link opens but I cannot see the photos.", "related_url": "https://lumispixel.com/galleries/example/"})
        ticket = SupportTicket.objects.get(requester=self.client_user)
        self.assertRedirects(response, reverse("support_ticket_detail", args=[ticket.reference]))
        self.assertEqual(ticket.requester_type, "client")
        self.assertEqual(ticket.queue, self.support_department)
        self.assertEqual(ticket.status, SupportTicket.Status.OPEN)
        follow = self.client.get(reverse("support_help_center"))
        self.assertContains(follow, ticket.reference)

    def test_customer_can_open_own_ticket_and_reply(self):
        ticket = SupportTicket.objects.create(requester=self.client_user, requester_type="client", category=SupportTicket.Category.ACCOUNT, subject="Account question", description="Please help.", queue=self.support_department)
        self.client.force_login(self.client_user)
        detail_url = reverse("support_ticket_detail", args=[ticket.reference])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Support thread")
        reply = self.client.post(detail_url, {"body": "Here is more information from me."})
        self.assertEqual(reply.status_code, 302)
        self.assertTrue(SupportTicketComment.objects.filter(ticket=ticket, author_user=self.client_user, is_internal=False, body__contains="more information").exists())

    def test_customer_cannot_open_another_customers_ticket(self):
        ticket = SupportTicket.objects.create(requester=self.client_user, requester_type="client", category=SupportTicket.Category.ACCOUNT, subject="Private issue", description="Private", queue=self.support_department)
        self.client.force_login(self.photographer_user)
        self.assertEqual(self.client.get(reverse("support_ticket_detail", args=[ticket.reference])).status_code, 404)

    def test_internal_notes_are_never_visible_to_customer(self):
        ticket = SupportTicket.objects.create(requester=self.client_user, requester_type="client", category=SupportTicket.Category.TECHNICAL, subject="Issue", description="Problem", queue=self.support_department)
        SupportTicketComment.objects.create(ticket=ticket, author_employee=self.employee, body="Private investigation note", is_internal=True)
        SupportTicketComment.objects.create(ticket=ticket, author_employee=self.employee, body="Public support reply", is_internal=False)
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("support_ticket_detail", args=[ticket.reference]))
        self.assertContains(response, "Public support reply")
        self.assertNotContains(response, "Private investigation note")

    def test_employee_public_reply_appears_in_customer_thread(self):
        ticket = SupportTicket.objects.create(requester=self.client_user, requester_type="client", category=SupportTicket.Category.TECHNICAL, subject="Unexpected error", description="The page returned an error.", queue=self.support_department)
        self.client.force_login(self.staff_user)
        response = self.client.post(reverse("internal_ops:ticket_detail", args=[ticket.reference]), {"action": "reply", "body": "We found the issue. Can you try again?"})
        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.WAITING_CUSTOMER)
        self.assertTrue(SupportTicketComment.objects.filter(ticket=ticket, author_employee=self.employee, is_internal=False).exists())
        self.assertTrue(InternalAuditEvent.objects.filter(action="internal.ticket.reply", target_id=ticket.reference).exists())
        self.client.force_login(self.client_user)
        customer_view = self.client.get(reverse("support_ticket_detail", args=[ticket.reference]))
        self.assertContains(customer_view, "We found the issue")

    def test_customer_reply_reopens_waiting_ticket(self):
        ticket = SupportTicket.objects.create(requester=self.client_user, requester_type="client", category=SupportTicket.Category.OTHER, subject="Follow up", description="Question", queue=self.support_department, status=SupportTicket.Status.WAITING_CUSTOMER)
        self.client.force_login(self.client_user)
        self.client.post(reverse("support_ticket_detail", args=[ticket.reference]), {"body": "I tried it and still need help."})
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.OPEN)

    def test_photographer_ticket_is_linked_to_photographer_account(self):
        self.client.force_login(self.photographer_user)
        self.client.post(reverse("support_help_center"), {"category": SupportTicket.Category.GALLERIES, "subject": "Upload stalled", "description": "A gallery upload is not progressing.", "related_url": ""})
        ticket = SupportTicket.objects.get(requester=self.photographer_user)
        self.assertEqual(ticket.requester_type, "photographer")
        self.assertEqual(ticket.queue.code, "customer-support")

    def test_employee_can_open_ticket_queue_and_customer_context(self):
        ticket = SupportTicket.objects.create(requester=self.client_user, requester_type="client", category=SupportTicket.Category.ACCOUNT, subject="Profile question", description="Need help with my profile.", queue=self.support_department)
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("internal_ops:tickets"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ticket.reference)
        detail = self.client.get(reverse("internal_ops:ticket_detail", args=[ticket.reference]))
        self.assertContains(detail, "Account context")
        self.assertContains(detail, "Customer conversation")

    def test_employee_can_assign_update_and_note_ticket(self):
        ticket = SupportTicket.objects.create(requester=self.client_user, requester_type="client", category=SupportTicket.Category.TECHNICAL, subject="Unexpected error", description="The page returned an error.", queue=self.support_department)
        self.client.force_login(self.staff_user)
        response = self.client.post(reverse("internal_ops:ticket_detail", args=[ticket.reference]), {"action": "update", "status": SupportTicket.Status.IN_PROGRESS, "priority": SupportTicket.Priority.HIGH, "queue": str(self.support_department.pk), "assignee": str(self.employee.pk), "due_at": ""})
        self.assertEqual(response.status_code, 302)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, SupportTicket.Status.IN_PROGRESS)
        self.client.post(reverse("internal_ops:ticket_detail", args=[ticket.reference]), {"action": "note", "body": "Reproduced and investigating."})
        self.assertTrue(SupportTicketComment.objects.filter(ticket=ticket, author_employee=self.employee, is_internal=True).exists())

    def test_non_employee_cannot_access_internal_ticket_operations(self):
        self.client.force_login(self.client_user)
        self.assertEqual(self.client.get(reverse("internal_ops:tickets")).status_code, 403)

    def test_superuser_can_access_ticket_operations_without_employee_profile(self):
        admin = User.objects.create_superuser(email="ticket-admin@lumispixel.com", password="test-pass-123")
        ticket = SupportTicket.objects.create(requester=self.client_user, requester_type="client", category=SupportTicket.Category.OTHER, subject="General question", description="Question", queue=self.support_department)
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("internal_ops:tickets")).status_code, 200)
        self.assertEqual(self.client.get(reverse("internal_ops:ticket_detail", args=[ticket.reference])).status_code, 200)
