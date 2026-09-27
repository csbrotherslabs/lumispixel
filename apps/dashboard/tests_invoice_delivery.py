from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, InvoiceActivity


class InvoiceDeliveryRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="invoice-delivery@example.com",
            password="test",
            email_verified=True,
            account_status=User.AccountStatus.ACTIVE,
            primary_role=User.PrimaryRole.PHOTOGRAPHER,
        )
        self.profile = PhotographerProfile.objects.create(
            user=self.user,
            slug="invoice-delivery-studio",
            onboarding_completed=True,
        )
        self.client_record = Client.objects.create(
            photographer=self.profile,
            first_name="Riley",
            email="riley-delivery@example.com",
        )
        self.client.force_login(self.user)

    def payload(self, intent="draft"):
        return {
            "client": self.client_record.pk,
            "issue_date": "2026-07-31",
            "due_date": "2026-08-30",
            "payment_terms": "30",
            "currency": "USD",
            "delivery_email": "on",
            "reminders_enabled": "on",
            "client_notes": "Client-facing note.",
            "terms": "Payment is due according to the schedule below.",
            "item_type[]": ["session"],
            "item_description[]": ["Portrait session"],
            "item_quantity[]": ["1"],
            "item_unit_price[]": ["250.00"],
            "item_discount[]": ["0"],
            "item_tax[]": ["0"],
            "schedule_label[]": ["Final payment"],
            "schedule_amount[]": ["250.00"],
            "schedule_due_date[]": ["2026-08-30"],
            "intent": intent,
        }

    def test_draft_save_never_sends_email(self):
        response = self.client.post(
            reverse("photographer_workspace:invoice_create"),
            self.payload(intent="draft"),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        invoice = ClientInvoice.objects.get()
        self.assertEqual(invoice.status, ClientInvoice.Status.DRAFT)
        self.assertIsNone(invoice.sent_at)
        self.assertFalse(InvoiceActivity.objects.filter(action="sent").exists())

    def test_zero_delivery_result_rolls_back_new_invoice(self):
        with patch("apps.dashboard.invoices.EmailMultiAlternatives.send", return_value=0):
            response = self.client.post(
                reverse("photographer_workspace:invoice_create"),
                self.payload(intent="send"),
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClientInvoice.objects.exists())
        self.assertFalse(InvoiceActivity.objects.exists())
        self.assertContains(response, "We couldn&#x27;t send this invoice email", status_code=400)
