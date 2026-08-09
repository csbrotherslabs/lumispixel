from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import PhotographerProfile, User
from apps.clients.models import Client, ClientInvoice, InvoiceActivity, InvoiceLineItem, InvoicePayment


class InvoiceWorkspaceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="invoice@example.com", password="test", email_verified=True,
            account_status=User.AccountStatus.ACTIVE, primary_role=User.PrimaryRole.PHOTOGRAPHER)
        self.profile = PhotographerProfile.objects.create(user=self.user, slug="invoice-studio", onboarding_completed=True)
        self.client_record = Client.objects.create(photographer=self.profile, first_name="Riley", email="riley@example.com")
        self.client.force_login(self.user)

    def payload(self, **changes):
        data = {"client": self.client_record.pk, "issue_date": "2026-07-31", "due_date": "2026-08-30",
            "payment_terms": "30", "currency": "USD", "delivery_email": "on", "reminders_enabled": "on",
            "item_type[]": ["session", "travel"], "item_description[]": ["Portrait session", "Travel"],
            "item_quantity[]": ["2", "1"], "item_unit_price[]": ["125.55", "40.00"],
            "item_discount[]": ["10", "0"], "item_tax[]": ["8.25", "0"], "intent": "draft"}
        data.update(changes)
        return data

    def test_server_calculates_decimal_totals_instead_of_accepting_client_total(self):
        response = self.client.post(reverse("photographer_workspace:invoice_create"), self.payload(total="0.01"))
        self.assertEqual(response.status_code, 302)
        invoice = ClientInvoice.objects.get()
        self.assertEqual(invoice.subtotal, Decimal("291.10"))
        self.assertEqual(invoice.discount_total, Decimal("25.11"))
        self.assertEqual(invoice.tax_total, Decimal("18.64"))
        self.assertEqual(invoice.total, Decimal("284.63"))
        self.assertEqual(invoice.line_items.count(), 2)
        self.assertTrue(invoice.invoice_number.startswith("INV-2026-"))

    def test_invalid_item_is_rejected_without_partial_invoice(self):
        response = self.client.post(reverse("photographer_workspace:invoice_create"), self.payload(**{"item_quantity[]": ["-1", "1"]}))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClientInvoice.objects.exists())

    def test_send_records_activity_and_locked_invoice_rejects_payment_or_void(self):
        response = self.client.post(reverse("photographer_workspace:invoice_create"), self.payload(intent="send"))
        invoice = ClientInvoice.objects.get()
        self.assertEqual(invoice.status, ClientInvoice.Status.SENT)
        self.assertEqual(InvoiceActivity.objects.get().action, "sent")
        self.client.post(reverse("photographer_workspace:invoice_action", args=[invoice.pk, "payment"]), {"amount": invoice.total})
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, ClientInvoice.Status.PAID)
        self.client.post(reverse("photographer_workspace:invoice_action", args=[invoice.pk, "void"]))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, ClientInvoice.Status.PAID)
        self.assertEqual(InvoicePayment.objects.count(), 1)

    def test_other_studio_cannot_view_invoice(self):
        invoice = ClientInvoice.objects.create(photographer=self.profile, client=self.client_record,
            invoice_number="INV-2026-9999", total=Decimal("10"))
        other_user = User.objects.create_user(email="other-invoice@example.com", password="test", email_verified=True,
            account_status=User.AccountStatus.ACTIVE, primary_role=User.PrimaryRole.PHOTOGRAPHER)
        PhotographerProfile.objects.create(user=other_user, slug="other-invoice", onboarding_completed=True)
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(reverse("photographer_workspace:invoice_view", args=[invoice.pk])).status_code, 404)

    def test_invoice_hub_distinguishes_empty_and_filtered_states(self):
        url = reverse("photographer_workspace:invoices")
        response = self.client.get(url)
        self.assertContains(response, "No invoices yet")
        self.assertNotContains(response, "Invoice summary")

        ClientInvoice.objects.create(photographer=self.profile, client=self.client_record,
            invoice_number="INV-OPEN", total=Decimal("125.00"), status=ClientInvoice.Status.SENT)
        response = self.client.get(url, {"q": "does-not-exist"})
        self.assertContains(response, "No invoices match these filters.")
        self.assertContains(response, "Clear Filters")
        self.assertNotContains(response, "Create your first invoice")

    def test_invoice_hub_filters_overdue_and_keeps_tenant_isolation(self):
        overdue = ClientInvoice.objects.create(photographer=self.profile, client=self.client_record,
            invoice_number="INV-OVERDUE", total=Decimal("250.00"), status=ClientInvoice.Status.SENT,
            due_date=timezone.localdate() - timedelta(days=2))
        ClientInvoice.objects.create(photographer=self.profile, client=self.client_record,
            invoice_number="INV-FUTURE", total=Decimal("100.00"), status=ClientInvoice.Status.SENT,
            due_date=timezone.localdate() + timedelta(days=2))
        other_user = User.objects.create_user(email="private@example.com", password="test", email_verified=True,
            account_status=User.AccountStatus.ACTIVE, primary_role=User.PrimaryRole.PHOTOGRAPHER)
        other_profile = PhotographerProfile.objects.create(user=other_user, slug="private-studio", onboarding_completed=True)
        other_client = Client.objects.create(photographer=other_profile, first_name="Private")
        ClientInvoice.objects.create(photographer=other_profile, client=other_client,
            invoice_number="PRIVATE-INVOICE", total=Decimal("9999"), status=ClientInvoice.Status.SENT)

        response = self.client.get(reverse("photographer_workspace:invoices"), {"status": "overdue"})
        self.assertContains(response, overdue.invoice_number)
        self.assertContains(response, "Overdue")
        self.assertNotContains(response, "INV-FUTURE")
        self.assertNotContains(response, "PRIVATE-INVOICE")
